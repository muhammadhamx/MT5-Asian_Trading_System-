import sys
import codecs

# Ensure stdout can handle UTF-8 (for emojis)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'trading': {
            'format': '%(asctime)s [TRADING] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'trading_bot.log',
            'formatter': 'verbose',
        },
        'trading_file': {
            'class': 'logging.FileHandler',
            'filename': 'trading_decisions.log',
            'formatter': 'trading',
        },
    },
    'loggers': {
        'trading_bot': {
            'handlers': ['console', 'file', 'trading_file'],
            'level': 'INFO',
        },
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}
