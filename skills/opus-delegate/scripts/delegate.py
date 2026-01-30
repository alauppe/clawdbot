#!/usr/bin/env python3
"""
opus-delegate: Run Claude CLI with Opus 4.5 for complex sub-tasks

Usage: delegate.py [options] "prompt"

Options:
    --model MODEL      Model to use (default: opus)
    --workdir DIR      Working directory (default: temp)
    --budget USD       Max budget (default: 5.00)
    --json             Output as JSON
    --system PROMPT    Custom system prompt
    --timeout SECS     Timeout in seconds (default: 300)
    --quiet            Suppress status messages
"""

import argparse
import os
import pty
import select
import subprocess
import sys
import tempfile


def run_with_pty(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    """Run command with a pseudo-terminal to satisfy TTY requirement."""
    output = []
    
    # Create pseudo-terminal
    master_fd, slave_fd = pty.openpty()
    
    try:
        process = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        
        # Read output with timeout
        import time
        start_time = time.time()
        
        while True:
            if timeout and (time.time() - start_time) > timeout:
                process.kill()
                return 124, "".join(output) + "\nError: Timeout"
            
            # Check if process has finished
            ret = process.poll()
            
            # Read available output
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if ready:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        output.append(data.decode('utf-8', errors='replace'))
                except OSError:
                    pass
            
            if ret is not None:
                # Process finished, read any remaining output
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        break
                    try:
                        data = os.read(master_fd, 4096)
                        if data:
                            output.append(data.decode('utf-8', errors='replace'))
                        else:
                            break
                    except OSError:
                        break
                break
        
        return process.returncode, "".join(output)
    
    finally:
        os.close(master_fd)


def clean_output(text: str) -> str:
    """Remove ANSI escape codes and control characters from output."""
    import re
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    # Remove OSC sequences (like ]9;4;0; or various terminal codes)
    text = re.sub(r'\][\d;:]+', '', text)
    # Remove xterm title sequences and similar
    text = re.sub(r'\[\?[\d;]+[a-zA-Z]', '', text)
    # Remove other control characters except newlines
    text = re.sub(r'[\x00-\x09\x0b-\x1f\x7f]', '', text)
    # Clean up any remaining garbage lines (terminal control sequences)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines that look like terminal control sequences (must have semicolon)
        if re.match(r'^[\d]+;[\d;:]*;?$', line.strip()):
            continue
        # Remove trailing terminal codes
        line = re.sub(r'[\[\]]\d*;?\d*;?\d*$', '', line)
        if line.strip():
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines).strip()


def main():
    parser = argparse.ArgumentParser(description='Delegate tasks to Claude CLI')
    parser.add_argument('prompt', nargs='?', help='The prompt to send')
    parser.add_argument('--model', default='opus', help='Model to use (default: opus)')
    parser.add_argument('--workdir', help='Working directory')
    parser.add_argument('--budget', default='5.00', help='Max budget in USD')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--system', help='Custom system prompt')
    parser.add_argument('--timeout', type=int, default=300, help='Timeout in seconds')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress status messages')
    
    args = parser.parse_args()
    
    if not args.prompt:
        parser.print_help()
        sys.exit(1)
    
    # Set up working directory
    if args.workdir:
        workdir = args.workdir
        cleanup_workdir = False
    else:
        workdir = tempfile.mkdtemp()
        cleanup_workdir = True
    
    # Build claude command
    cmd = [
        'claude',
        '--print',
        '--model', args.model,
        '--max-budget-usd', args.budget,
        '--permission-mode', 'bypassPermissions',
    ]
    
    if args.json:
        cmd.extend(['--output-format', 'json'])
    
    if args.system:
        cmd.extend(['--system-prompt', args.system])
    
    cmd.append(args.prompt)
    
    # Status message
    if not args.quiet:
        print(f"🧠 Delegating to {args.model}...", file=sys.stderr)
    
    # Change to working directory
    original_dir = os.getcwd()
    os.chdir(workdir)
    
    try:
        exit_code, output = run_with_pty(cmd, args.timeout)
        
        # Clean and print output
        cleaned = clean_output(output)
        if cleaned:
            print(cleaned)
        
        return exit_code
    
    finally:
        os.chdir(original_dir)
        if cleanup_workdir:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main() or 0)
