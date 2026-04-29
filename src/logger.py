"""
Centralized logging system with colors and filtered events
"""
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Foreground colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output"""
    
    # Color mapping for log levels
    LEVEL_COLORS = {
        'DEBUG': Colors.GRAY,
        'INFO': Colors.CYAN,
        'SUCCESS': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.BOLD + Colors.RED,
    }
    
    # Color mapping for logger names
    LOGGER_COLORS = {
        'commands.play': Colors.BLUE,
        'commands.playback': Colors.BLUE,
        'commands.queue': Colors.BLUE,
        'src.player': Colors.GREEN,
        'src.providers': Colors.MAGENTA,
        'events': Colors.CYAN,
        'discord.voice_state': Colors.GRAY,  # Dimmed
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors"""
        # Get level color
        level_color = self.LEVEL_COLORS.get(record.levelname, Colors.WHITE)
        
        # Get logger color
        logger_color = Colors.WHITE
        for logger_name, color in self.LOGGER_COLORS.items():
            if record.name.startswith(logger_name):
                logger_color = color
                break
        
        # Format timestamp
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')
        
        # Build colored format
        colored_level = f"{level_color}{record.levelname:8s}{Colors.RESET}"
        colored_logger = f"{logger_color}{record.name}{Colors.RESET}"
        colored_message = record.getMessage()
        
        # Add extra color to important messages
        if 'error' in colored_message.lower() or 'failed' in colored_message.lower():
            colored_message = f"{Colors.RED}{colored_message}{Colors.RESET}"
        elif 'connected' in colored_message.lower() or 'success' in colored_message.lower():
            colored_message = f"{Colors.GREEN}{colored_message}{Colors.RESET}"
        
        return f"{timestamp} [{colored_level}] {colored_logger}: {colored_message}"


class BotLogFilter(logging.Filter):
    """Filter to reduce noise from unnecessary logs"""
    
    # Messages to suppress
    SUPPRESS_PATTERNS = [
        'voice_state',  # Other members' voice state updates
        'Shard ID',     # Discord gateway shard info
        'Starting voice handshake',  # Verbose connection logs
        'Voice handshake complete',  # Verbose connection logs
        'discord.client',  # Token logging
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out noisy logs"""
        message = record.getMessage()
        
        # Suppress voice state updates for non-bot members
        if 'voice state update' in message.lower() and 'MeigherBot' not in message:
            return False
        
        # Suppress gateway connection noise
        if any(pattern.lower() in message.lower() for pattern in self.SUPPRESS_PATTERNS):
            if 'discord.client' in record.name or 'discord.gateway' in record.name:
                return False
        
        return True


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Setup centralized logging with colored console and optional file output
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file (default: None)
    """
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter())
    console_handler.addFilter(BotLogFilter())
    root_logger.addHandler(console_handler)
    
    # File handler (if specified) - no colors, daily rotation, 7-day retention
    if log_file:
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='D',
            interval=1,
            backupCount=7,
            encoding='utf-8',
            utc=False,
        )
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Set discord.py loggers to WARNING to reduce noise
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    
    # Keep voice state at WARNING but filter updates for other members
    logging.getLogger('discord.voice_state').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


# Quick access loggers for common modules
logger_play = get_logger('commands.play')
logger_player = get_logger('src.player')
logger_providers = get_logger('src.providers')
logger_events = get_logger('events')
logger_queue = get_logger('src.queue')
