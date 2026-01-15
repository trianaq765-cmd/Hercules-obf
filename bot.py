import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import subprocess
import os
import uuid
import io
import time
from datetime import datetime
from config import Config

intents = discord.Intents.default()
intents.message_content = True

class ObfuscatorBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=Config.BOT_PREFIX, intents=intents, help_command=None)
        self.start_time = datetime.utcnow()
        self.stats = {'total': 0, 'success': 0, 'failed': 0}
        self.cooldowns = {}
    
    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced!")
    
    async def on_ready(self):
        print(f'Bot ready: {self.user} | Servers: {len(self.guilds)}')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="/help | Lua Obfuscator"
            )
        )

bot = ObfuscatorBot()

# ============ HELPER FUNCTIONS ============

def create_embed(title: str, desc: str, color: int = 0xff6b6b) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=desc,
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Hercules Obfuscator v1.6")
    return embed

def check_cooldown(user_id: int) -> tuple:
    if str(user_id) in Config.ADMIN_IDS:
        return False, 0
    now = datetime.utcnow()
    if user_id in bot.cooldowns:
        diff = (now - bot.cooldowns[user_id]).total_seconds()
        if diff < Config.COOLDOWN_SECONDS:
            return True, int(Config.COOLDOWN_SECONDS - diff)
    bot.cooldowns[user_id] = now
    return False, 0

async def download_attachment(attachment) -> tuple:
    if attachment.size > Config.MAX_FILE_SIZE:
        return None, f"File too large (max {Config.MAX_FILE_SIZE // 1024 // 1024}MB)"
    if not attachment.filename.endswith(('.lua', '.txt')):
        return None, "Invalid file type. Use .lua or .txt"
    try:
        content = await attachment.read()
        return content.decode('utf-8'), None
    except Exception as e:
        return None, f"Failed to read file: {str(e)}"

# ============ OBFUSCATOR FUNCTION ============

async def run_obfuscator(
    code: str,
    preset: str = None,
    modules: dict = None
) -> dict:
    """Run Hercules obfuscator"""
    req_id = str(uuid.uuid4())
    input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
    
    try:
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)
        
        with open(input_file, 'w') as f:
            f.write(code)
        
        # Build command
        cmd = ['lua', 'hercules.lua', input_file]
        
        if preset:
            cmd.append(f'--{preset}')
        elif modules:
            module_flags = {
                'string_encoding': '--stringencoding',
                'variable_renaming': '--variablerenaming',
                'control_flow': '--controlflow',
                'garbage_code': '--garbagecode',
                'opaque_predicates': '--opaquepredicates',
                'function_inlining': '--functioninlining',
                'dynamic_code': '--dynamiccode',
                'bytecode_encoding': '--bytecodeencoding',
                'compressor': '--compressor',
                'wrap_in_function': '--wrapinfunction',
                'virtual_machine': '--virtualmachine',
                'antitamper': '--antitamper',
                'string_to_expressions': '--stringtoexpressions',
                'watermark': '--watermark',
            }
            
            for module, enabled in modules.items():
                if enabled and module in module_flags:
                    cmd.append(module_flags[module])
        
        start_time = time.time()
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=Config.HERCULES_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=Config.OBFUSCATION_TIMEOUT
        )
        
        elapsed = time.time() - start_time
        
        # Find output file
        output_file = input_file.replace('.lua', '_obfuscated.lua')
        if not os.path.exists(output_file):
            output_file = os.path.join(Config.HERCULES_PATH, f'{req_id}_obfuscated.lua')
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                output = f.read()
            
            original_size = len(code)
            obfuscated_size = len(output)
            size_increase = ((obfuscated_size - original_size) / original_size * 100) if original_size > 0 else 0
            
            return {
                'success': True,
                'output': output,
                'time_taken': f"{elapsed:.2f}s",
                'original_size': original_size,
                'obfuscated_size': obfuscated_size,
                'size_increase': f"{size_increase:.2f}%"
            }
        else:
            error_msg = stderr.decode() if stderr else stdout.decode() if stdout else 'Obfuscation failed'
            return {'success': False, 'error': error_msg}
    
    except asyncio.TimeoutError:
        return {'success': False, 'error': 'Timeout (5 min limit)'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        # Cleanup
        for f in [input_file, input_file.replace('.lua', '_obfuscated.lua')]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

# ============ SLASH COMMANDS ============

@bot.tree.command(name="obfuscate", description="Obfuscate Lua code")
@app_commands.describe(
    code="The Lua code to obfuscate",
    preset="Obfuscation preset level",
    file="Upload a .lua file instead"
)
@app_commands.choices(preset=[
    app_commands.Choice(name="Minimum - Light obfuscation", value="min"),
    app_commands.Choice(name="Medium - Balanced (default)", value="mid"),
    app_commands.Choice(name="Maximum - Heavy obfuscation", value="max"),
])
async def slash_obfuscate(
    interaction: discord.Interaction,
    code: str = None,
    preset: str = "mid",
    file: discord.Attachment = None
):
    on_cd, remaining = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {remaining} seconds", 0xffc800),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    if file:
        content, error = await download_attachment(file)
        if error:
            await interaction.followup.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await interaction.followup.send(
            embed=create_embed("❌ Error", "Provide code or upload a file", 0xff6464)
        )
        return
    
    if len(code) > Config.MAX_CODE_LENGTH:
        await interaction.followup.send(
            embed=create_embed("❌ Error", "Code too long (max 500k chars)", 0xff6464)
        )
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(
        embed=create_embed("🔄 Obfuscating", f"Preset: `{preset}`\nPlease wait...", 0xffc800)
    )
    
    result = await run_obfuscator(code, preset=preset)
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        embed = create_embed(
            "✅ Obfuscation Complete",
            f"**Preset:** `{preset}`",
            0x00ff64
        )
        embed.add_field(name="⏱️ Time", value=f"`{result['time_taken']}`", inline=True)
        embed.add_field(name="📥 Original", value=f"`{result['original_size']:,}` bytes", inline=True)
        embed.add_field(name="📤 Obfuscated", value=f"`{result['obfuscated_size']:,}` bytes", inline=True)
        embed.add_field(name="📈 Increase", value=f"`{result['size_increase']}`", inline=True)
        
        await msg.edit(embed=embed)
        await interaction.followup.send(
            file=discord.File(io.BytesIO(output.encode()), filename="obfuscated.lua")
        )
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.tree.command(name="obfuscate-custom", description="Obfuscate with custom module selection")
@app_commands.describe(
    file="Upload the .lua file to obfuscate",
    watermark="Add watermark",
    control_flow="Control flow obfuscation",
    variable_renaming="Rename variables",
    garbage_code="Insert garbage code",
    string_encoding="Encode strings",
    compressor="Compress output",
    virtual_machine="VM protection",
    antitamper="Anti-tamper protection"
)
async def slash_obfuscate_custom(
    interaction: discord.Interaction,
    file: discord.Attachment,
    watermark: bool = True,
    control_flow: bool = True,
    variable_renaming: bool = True,
    garbage_code: bool = True,
    string_encoding: bool = False,
    compressor: bool = True,
    virtual_machine: bool = False,
    antitamper: bool = False
):
    on_cd, remaining = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {remaining} seconds", 0xffc800),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    content, error = await download_attachment(file)
    if error:
        await interaction.followup.send(embed=create_embed("❌ Error", error, 0xff6464))
        return
    
    modules = {
        'watermark': watermark,
        'control_flow': control_flow,
        'variable_renaming': variable_renaming,
        'garbage_code': garbage_code,
        'string_encoding': string_encoding,
        'compressor': compressor,
        'virtual_machine': virtual_machine,
        'antitamper': antitamper,
        'opaque_predicates': True,
        'wrap_in_function': True,
    }
    
    enabled_modules = [k for k, v in modules.items() if v]
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(
        embed=create_embed(
            "🔄 Custom Obfuscation",
            f"**Modules:** {len(enabled_modules)}\n`{', '.join(enabled_modules[:5])}{'...' if len(enabled_modules) > 5 else ''}`",
            0xffc800
        )
    )
    
    result = await run_obfuscator(content, modules=modules)
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        embed = create_embed("✅ Custom Obfuscation Complete", "", 0x00ff64)
        embed.add_field(name="📦 Modules", value=f"`{len(enabled_modules)}`", inline=True)
        embed.add_field(name="⏱️ Time", value=f"`{result['time_taken']}`", inline=True)
        embed.add_field(name="📈 Increase", value=f"`{result['size_increase']}`", inline=True)
        embed.add_field(
            name="📊 Size",
            value=f"`{result['original_size']:,}` → `{result['obfuscated_size']:,}` bytes",
            inline=False
        )
        
        await msg.edit(embed=embed)
        await interaction.followup.send(
            file=discord.File(io.BytesIO(output.encode()), filename=f"obf_{file.filename}")
        )
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.tree.command(name="obfuscate-max", description="Maximum obfuscation (VM + Anti-Tamper)")
@app_commands.describe(file="Upload the .lua file")
async def slash_obfuscate_max(interaction: discord.Interaction, file: discord.Attachment):
    on_cd, remaining = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {remaining} seconds", 0xffc800),
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    content, error = await download_attachment(file)
    if error:
        await interaction.followup.send(embed=create_embed("❌ Error", error, 0xff6464))
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(
        embed=create_embed(
            "🔄 Maximum Obfuscation",
            "**Enabled:** All modules + VM + Anti-Tamper\n⚠️ This may take longer...",
            0xffc800
        )
    )
    
    result = await run_obfuscator(content, preset='max')
    
    if result['success']:
        bot.stats['success'] += 1
        output = result['output']
        
        embed = create_embed(
            "✅ Maximum Obfuscation Complete",
            "🛡️ **All protections enabled**",
            0x00ff64
        )
        embed.add_field(name="⏱️ Time", value=f"`{result['time_taken']}`", inline=True)
        embed.add_field(name="📈 Increase", value=f"`{result['size_increase']}`", inline=True)
        embed.add_field(
            name="📊 Size",
            value=f"`{result['original_size']:,}` → `{result['obfuscated_size']:,}` bytes",
            inline=False
        )
        
        await msg.edit(embed=embed)
        await interaction.followup.send(
            file=discord.File(io.BytesIO(output.encode()), filename=f"max_obf_{file.filename}")
        )
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.tree.command(name="help", description="Show help information")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡️ Hercules Obfuscator v1.6",
        description="Powerful Lua Obfuscation Bot",
        color=0xff6b6b,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="📝 Commands",
        value="""
`/obfuscate` - Quick obfuscate with presets
`/obfuscate-custom` - Custom module selection
`/obfuscate-max` - Maximum protection
`/modules` - List all modules
`/stats` - View statistics
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚡ Presets",
        value="""
• `min` - Light (Variable Renaming, Garbage Code)
• `mid` - Balanced (+ Control Flow, Compressor)
• `max` - Heavy (+ VM, Anti-Tamper, All modules)
        """,
        inline=False
    )
    
    embed.add_field(
        name="💬 Quick Commands",
        value="""
`!obf <code>` - Quick obfuscate
`!obf-max` - Max obfuscation (attach file)
        """,
        inline=False
    )
    
    embed.set_footer(text="Hercules Obfuscator v1.6")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="modules", description="List all obfuscation modules")
async def slash_modules(interaction: discord.Interaction):
    embed = create_embed("🔧 Obfuscation Modules", "Available modules in Hercules")
    
    modules = [
        ("🏷️ Watermark", "Adds attribution watermark"),
        ("🔤 String Encoding", "Encodes string literals"),
        ("🔢 String to Expressions", "Converts strings to math expressions"),
        ("🔀 Control Flow", "Obfuscates program flow"),
        ("📝 Variable Renaming", "Renames variables to random names"),
        ("🗑️ Garbage Code", "Inserts dead/fake code"),
        ("🔮 Opaque Predicates", "Adds confusing conditions"),
        ("📦 Function Inlining", "Inlines function calls"),
        ("⚡ Dynamic Code", "Generates dynamic code paths"),
        ("💾 Bytecode Encoding", "Encodes to bytecode"),
        ("🗜️ Compressor", "Compresses the output"),
        ("📦 Wrap in Function", "Wraps code in function"),
        ("🖥️ Virtual Machine", "VM protection layer"),
        ("🛡️ Anti-Tamper", "Tamper detection"),
    ]
    
    for name, desc in modules:
        embed.add_field(name=name, value=desc, inline=True)
    
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stats", description="View bot statistics")
async def slash_stats(interaction: discord.Interaction):
    uptime = datetime.utcnow() - bot.start_time
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    mins, secs = divmod(rem, 60)
    days, hours = divmod(hours, 24)
    
    uptime_str = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m {secs}s"
    success_rate = (bot.stats['success'] / bot.stats['total'] * 100) if bot.stats['total'] > 0 else 0
    
    embed = create_embed("📊 Bot Statistics", "")
    embed.add_field(name="📈 Total", value=f"`{bot.stats['total']}`", inline=True)
    embed.add_field(name="✅ Success", value=f"`{bot.stats['success']}`", inline=True)
    embed.add_field(name="❌ Failed", value=f"`{bot.stats['failed']}`", inline=True)
    embed.add_field(name="📊 Rate", value=f"`{success_rate:.1f}%`", inline=True)
    embed.add_field(name="🌐 Servers", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
    
    await interaction.response.send_message(embed=embed)


# ============ PREFIX COMMANDS ============

@bot.command(name='obf')
async def cmd_obf(ctx, *, code: str = None):
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        content, error = await download_attachment(attachment)
        if error:
            await ctx.send(embed=create_embed("❌ Error", error, 0xff6464))
            return
        code = content
    
    if not code:
        await ctx.send(embed=create_embed("❌ Error", "Usage: `!obf <code>` or attach a file", 0xff6464))
        return
    
    on_cd, remaining = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳ Cooldown", f"Wait {remaining}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 Obfuscating", "Using medium preset...", 0xffc800))
    
    result = await run_obfuscator(code, preset='mid')
    
    if result['success']:
        bot.stats['success'] += 1
        embed = create_embed(
            "✅ Obfuscation Complete",
            f"**Time:** `{result['time_taken']}`\n**Size:** `{result['original_size']:,}` → `{result['obfuscated_size']:,}` bytes",
            0x00ff64
        )
        await msg.edit(embed=embed)
        await ctx.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.command(name='obf-max')
async def cmd_obf_max(ctx):
    if not ctx.message.attachments:
        await ctx.send(embed=create_embed("❌ Error", "Attach a .lua file", 0xff6464))
        return
    
    attachment = ctx.message.attachments[0]
    content, error = await download_attachment(attachment)
    if error:
        await ctx.send(embed=create_embed("❌ Error", error, 0xff6464))
        return
    
    on_cd, remaining = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳ Cooldown", f"Wait {remaining}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 Maximum Obfuscation", "This may take a while...", 0xffc800))
    
    result = await run_obfuscator(content, preset='max')
    
    if result['success']:
        bot.stats['success'] += 1
        await msg.edit(embed=create_embed(
            "✅ Maximum Obfuscation Complete",
            f"**Size:** `{result['original_size']:,}` → `{result['obfuscated_size']:,}` bytes (+{result['size_increase']})",
            0x00ff64
        ))
        await ctx.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="max_obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.command(name='help')
async def cmd_help(ctx):
    embed = discord.Embed(title="🛡️ Hercules Obfuscator", color=0xff6b6b)
    embed.add_field(
        name="Commands",
        value="""
`/obfuscate` - Obfuscate with presets
`/obfuscate-custom` - Custom modules
`/obfuscate-max` - Maximum protection
`!obf <code>` - Quick obfuscate
`!obf-max` - Max obfuscation (attach file)
        """,
        inline=False
    )
    await ctx.send(embed=embed)


# ============ ERROR HANDLERS ============

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(embed=create_embed("❌ Error", str(error)[:200], 0xff6464))

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=create_embed("❌ Error", str(error)[:200], 0xff6464),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=create_embed("❌ Error", str(error)[:200], 0xff6464),
                ephemeral=True
            )
    except:
        pass


# ============ RUN BOT ============

if __name__ == '__main__':
    if not Config.DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        exit(1)
    
    print("Starting Hercules Obfuscator Bot...")
    bot.run(Config.DISCORD_TOKEN)
