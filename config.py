import os

class Config:
    # Discord
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    BOT_PREFIX = os.getenv('BOT_PREFIX', '!')
    
    # Paths
    HERCULES_PATH = '/app/hercules/src'
    UPLOAD_FOLDER = '/app/uploads'
    OUTPUT_FOLDER = '/app/outputs'
    
    # Limits
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_CODE_LENGTH = 500000
    OBFUSCATION_TIMEOUT = 300  # 5 minutes
    COOLDOWN_SECONDS = 30
    
    # Web
    WEB_PORT = int(os.getenv('PORT', 10000))
    
    # Admin
    ADMIN_IDS = [x.strip() for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
    
    # Obfuscation Presets
    PRESETS = {
        'min': {
            'watermark': True,
            'variable_renaming': True,
            'garbage_code': True,
        },
        'mid': {
            'watermark': True,
            'string_encoding': True,
            'variable_renaming': True,
            'control_flow': True,
            'garbage_code': True,
            'opaque_predicates': True,
            'compressor': True,
        },
        'max': {
            'watermark': True,
            'string_to_expressions': True,
            'control_flow': True,
            'variable_renaming': True,
            'garbage_code': True,
            'opaque_predicates': True,
            'function_inlining': True,
            'compressor': True,
            'wrap_in_function': True,
            'virtual_machine': True,
            'antitamper': True,
        }
    }
