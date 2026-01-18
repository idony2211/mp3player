# MP3 Player

A Python-based MP3 player application with advanced features including speech-to-text transcription using Whisper.

## Requirements

- Python 3.12 (or compatible version)
- Virtual environment (venv) - already set up in the `venv/` directory
- CUDA-compatible GPU (recommended for faster transcription)
- Linux platform

## Dependencies

The project uses the following key libraries (already installed in venv):

- torch: Deep learning framework
- faster-whisper: Speech-to-text transcription
- ctranslate2: Fast inference engine
- huggingface_hub: Model hub integration
- av: Audio/video processing
- typer: CLI framework
- And other dependencies listed in the virtual environment

## Installation

1. Ensure Python 3.12 is installed on your system.
2. The virtual environment is already configured in the `venv/` directory.
3. If needed, recreate the virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt  # Note: requirements.txt not included, dependencies are pre-installed
   ```

## Running the Project

1. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

2. Run the application:
   ```bash
   python main.py
   ```

The application will start and log information to the `logs/` directory.

## Backing Up to GitHub

This project is already a Git repository. To push changes to GitHub using SSH:

1. Ensure you have a GitHub repository set up (create one at https://github.com if not already done).

2. Set up SSH keys if you haven't already:
   - Generate SSH key: `ssh-keygen -t ed25519 -C "your_email@example.com"`
   - Add to ssh-agent: `eval "$(ssh-agent -s)"` and `ssh-add ~/.ssh/id_ed25519`
   - Add public key to GitHub: Copy `~/.ssh/id_ed25519.pub` to GitHub Settings > SSH and GPG keys

3. Add the remote repository (replace `YOUR_USERNAME` and `YOUR_REPO_NAME`):
   ```bash
   git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git
   ```

4. Add and commit your changes:
   ```bash
   git add .
   git commit -m "Initial commit"
   ```

5. Push to GitHub:
   ```bash
   git push -u origin main
   ```

If you encounter SSH issues, verify your SSH key setup with `ssh -T git@github.com`.

## Project Structure

- `main.py`: Main entry point
- `mp3player/`: Core package (implementation details)
- `files/`: Directory for MP3 files and markers
- `logs/`: Application logs
- `venv/`: Python virtual environment
