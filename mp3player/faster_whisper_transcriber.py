"""
Faster-whisper transcription service using CTranslate2.
Uses PyAV for audio decoding (bundled FFmpeg libraries).
"""

import logging
import os
import threading
import traceback
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

os.environ["HF_HUB_OFFLINE"] = "1"

# Set environment variables to avoid cuDNN compatibility issues on older GPUs
# This helps with GTX 1060 (Pascal) and cuDNN 9.1
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

# Set LD_LIBRARY_PATH for NVIDIA libraries
try:
    import nvidia.cublas.lib
    import nvidia.cudnn.lib
    ld_path = os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__)
    os.environ["LD_LIBRARY_PATH"] = ld_path
    logger.info(f"[DEBUG] Set LD_LIBRARY_PATH: {ld_path}")
except ImportError:
    pass


class FasterWhisperTranscriber:
    """
    Wrapper for faster-whisper transcription.
    Faster implementation of OpenAI's Whisper using CTranslate2.
    """

    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        model_path: str = "",
        compute_type: Optional[str] = None,
        beam_size: int = 5,
    ):
        """
        Initialize the faster-whisper transcriber.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: Device to use (cuda, cpu)
            model_path: Custom model directory path (optional)
            compute_type: Compute type for model (float32, int8, int8_float16, float16).
                          Default is None which tries multiple types. Use float32 for Pascal GPUs.
                          Can also be set via WHISPER_COMPUTE_TYPE environment variable.
            beam_size: Beam size for decoding (default 5). Higher values may improve accuracy but slower.
        """
        self.model_size = model_size
        self.model_path = model_path
        self.beam_size = beam_size
        self.model = None
        self.cpu_model = None
        self.is_loading = False

        if compute_type is None:
            compute_type = os.environ.get("WHISPER_COMPUTE_TYPE")
        self.compute_type = compute_type

        if device is None:
            try:
                import torch

                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
        else:
            self.device = device

        # Configure PyTorch to be conservative with cuDNN
        try:
            import torch

            if torch.cuda.is_available():
                force_disable_cudnn = os.environ.get("DISABLE_CUDNN") == "1"
                if force_disable_cudnn:
                    torch.backends.cudnn.enabled = False
                    logger.info("[DEBUG] DISABLE_CUDNN=1 set - cuDNN disabled")
                else:
                    torch.backends.cudnn.enabled = True
                    torch.backends.cudnn.benchmark = False
                    torch.backends.cudnn.deterministic = True
                    logger.info("[DEBUG] Configured conservative cuDNN settings")
        except ImportError:
            pass

        logger.info(f"[DEBUG] Using device: {self.device}")

    def _load_model(self) -> bool:
        """
        Load the faster-whisper model with fallback support.

        Returns:
            True if model loaded successfully, False otherwise
        """
        if self.model is not None:
            return True

        if self.is_loading:
            return False

        try:
            from faster_whisper import WhisperModel

            self.is_loading = True

            # For GTX 1060 (Pascal) and similar GPUs, skip GPU to avoid cuDNN errors
            # Use CPU directly instead of trying GPU first
            skip_gpu = self._should_skip_gpu()

            if self.device == "cpu" or skip_gpu:
                logger.info("[DEBUG] Using CPU directly")
                result = self._load_cpu_model()
                self.is_loading = False
                return result

            # Try GPU first, then fallback to CPU
            compute_types = ["int8", "int8_float16", "float16", "float32"]

            if self.compute_type:
                compute_types = [self.compute_type]
                logger.info(
                    f"[DEBUG] Using specified compute_type: {self.compute_type}"
                )

            for compute_type in compute_types:
                for device in [self.device, "cpu"]:
                    if compute_type in ["float16", "int8_float16"] and device == "cpu":
                        continue

                    logger.info(
                        f"[DEBUG] Loading faster-whisper model: {self.model_size} on {device} with {compute_type}"
                    )

                    try:
                        if self.model_path:
                            model = WhisperModel(
                                self.model_path,
                                device=device,
                                compute_type=compute_type,
                            )
                        else:
                            model = WhisperModel(
                                self.model_size,
                                device=device,
                                compute_type=compute_type,
                            )

                        if device == "cpu":
                            self.cpu_model = model
                        else:
                            self.model = model

                        logger.info(
                            f"[DEBUG] faster-whisper model loaded successfully with {compute_type} on {device}"
                        )
                        self.is_loading = False
                        return True
                    except Exception as e:
                        logger.warning(
                            f"[DEBUG] Failed with {compute_type} on {device}: {e}"
                        )
                        if device == "cpu":
                            raise

            self.is_loading = False
            return False
        except ImportError as e:
            logger.error(f"[DEBUG] faster-whisper import error: {e}")
            logger.error(
                "[DEBUG] faster-whisper not installed. Install with: pip install faster-whisper"
            )
            self.is_loading = False
            return False
        except Exception as e:
            self.is_loading = False
            logger.error(f"[DEBUG] Failed to load faster-whisper model: {e}")
            return False

    def _should_skip_gpu(self) -> bool:
        """
        Check if we should skip GPU due to known compatibility issues.

        Returns:
            True if GPU should be skipped, False otherwise
        """
        if self.device != "cuda":
            return False

        try:
            import torch

            if not torch.cuda.is_available():
                return False

            # Check for FORCE_GPU environment variable to override GPU compatibility check
            if os.environ.get("FORCE_GPU") == "1":
                logger.info(
                    "[DEBUG] FORCE_GPU=1 set - skipping GPU compatibility check"
                )
                return False

            # Check for GTX 1060 (Pascal architecture) which has cuDNN issues
            gpu_name = torch.cuda.get_device_name(0)
            gpu_arch = torch.cuda.get_arch_list()

            # Known problematic GPUs with cuDNN 9.1
            # Temporarily allowing GTX 1060 to try GPU
            # if "1060" in gpu_name or "Pascal" in " ".join(gpu_arch):
            #     logger.info(
            #         f"[DEBUG] Detected {gpu_name} - skipping GPU to avoid cuDNN errors. Set FORCE_GPU=1 to override."
            #     )
            #     return True

            return False
        except Exception as e:
            logger.warning(f"[DEBUG] Could not check GPU compatibility: {e}")
            return False

    def _load_cpu_model(self) -> bool:
        """
        Load model directly on CPU.

        Returns:
            True if model loaded successfully, False otherwise
        """
        try:
            from faster_whisper import WhisperModel

            compute_type = self.compute_type if self.compute_type else "int8"
            logger.info(
                f"[DEBUG] Loading faster-whisper model: cpu with {compute_type}"
            )
            model = WhisperModel(
                self.model_size if not self.model_path else self.model_path,
                device="cpu",
                compute_type=compute_type,
            )
            self.cpu_model = model
            self.model = model
            logger.info("[DEBUG] CPU model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"[DEBUG] Failed to load CPU model: {e}")
            return False

    def transcribe(
        self, audio_path: str, progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        Transcribe an audio file using faster-whisper.

        Args:
            audio_path: Path to the audio file
            progress_callback: Optional callback for progress updates

        Returns:
            Transcribed text, or None if transcription failed
        """
        if not self._load_model():
            if progress_callback:
                progress_callback("Error: faster-whisper not available")
            return None

        try:
            if progress_callback:
                progress_callback("Transcribing...")

            logger.info(f"[DEBUG] Starting transcription of: {audio_path}")
            logger.info(f"[DEBUG] Model loaded: {self.model is not None}")

            return self._do_transcribe(audio_path, progress_callback)

        except ImportError as e:
            logger.error(f"[DEBUG] Import error during transcription: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"[DEBUG] Transcription failed: {e}")

            if "cuDNN" in str(e) and self.device == "cuda":
                logger.info("[DEBUG] GPU transcription failed, falling back to CPU...")
                return self._transcribe_with_cpu_fallback(audio_path, progress_callback)

            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return None

    def _do_transcribe(
        self, audio_path: str, progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """Actual transcription implementation."""
        segments, info = self.model.transcribe(
            audio_path, language="en", beam_size=self.beam_size, vad_filter=False
        )

        logger.info(
            f"[DEBUG] Detected language: {info.language} (probability: {info.language_probability})"
        )

        text_parts = []
        for segment in segments:
            segment_text = segment.text.strip()
            if segment_text:
                text_parts.append(segment_text)

        text = " ".join(text_parts).strip()
        logger.info(f"[DEBUG] Extracted text length: {len(text)}")

        if progress_callback:
            progress_callback("Transcription complete")

        logger.info(f"[DEBUG] Transcribed audio: {len(text)} characters")
        return text

    def _transcribe_with_cpu_fallback(
        self, audio_path: str, progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """Fallback to CPU if GPU transcription fails."""
        if progress_callback:
            progress_callback("Retrying with CPU...")

        if self.cpu_model is None:
            logger.info("[DEBUG] Loading CPU model for fallback...")
            try:
                from faster_whisper import WhisperModel

                self.cpu_model = WhisperModel(
                    self.model_size, device="cpu", compute_type="int8"
                )
            except Exception as e:
                logger.error(f"[DEBUG] Failed to load CPU model: {e}")
                if progress_callback:
                    progress_callback(f"Error: {str(e)}")
                return None

        logger.info("[DEBUG] Using cached CPU model...")
        segments, info = self.cpu_model.transcribe(
            audio_path, language="en", beam_size=self.beam_size, vad_filter=False
        )

        logger.info(
            f"[DEBUG] Detected language: {info.language} (probability: {info.language_probability})"
        )

        text_parts = []
        for segment in segments:
            segment_text = segment.text.strip()
            if segment_text:
                text_parts.append(segment_text)

        text = " ".join(text_parts).strip()
        logger.info(f"[DEBUG] CPU fallback transcription: {len(text)} characters")

        if progress_callback:
            progress_callback("Transcription complete")

        return text

    def transcribe_async(
        self,
        audio_path: str,
        on_complete: Callable[[Optional[str]], None],
        on_error: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Transcribe an audio file asynchronously.
        """

        def run_transcription():
            try:
                logger.info("[DEBUG] Starting async transcription thread")
                result = self.transcribe(audio_path, progress_callback)
                if result is not None:
                    on_complete(result)
                else:
                    if on_error:
                        on_error("Transcription returned None")
                    on_complete(None)
            except Exception as e:
                logger.error(f"[DEBUG] Async transcription error: {e}")
                if on_error:
                    on_error(str(e))
                on_complete(None)

        thread = threading.Thread(target=run_transcription, daemon=True)
        thread.start()
