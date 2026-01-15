import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import uuid
import io
import time
from datetime import datetime
from config import Config

intents = discord.Intents.default()
intents.message_content = True

class Bot(commands.Bot):
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
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="/help"))

bot = Bot()

def create_embed(title, desc, color=0xff6b6b):
    embed = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.utcnow())
    embed.set_footer(text="Hercules Obfuscator")
    return embed

def check_cooldown(user_id):
    if str(user_id) in Config.ADMIN_IDS:
        return False, 0
    now = datetime.utcnow()
    if user_id in bot.cooldowns:
        diff = (now - bot.cooldowns[user_id]).total_seconds()
        if diff < Config.COOLDOWN_SECONDS:
            return True, int(Config.COOLDOWN_SECONDS - diff)
    bot.cooldowns[user_id] = now
    return False, 0

async def download_attachment(att):
    if att.size > Config.MAX_FILE_SIZE:
        return None, "File too large (max 5MB)"
    if not att.filename.endswith(('.lua', '.txt')):
        return None, "Use .lua or .txt"
    try:
        return (await att.read()).decode('utf-8'), None
    except:
        return None, "Failed to read"

# Preset configurations - using safe modules only
PRESETS = {
    'min': ['--varrenaming', '--garbagecode'],
    'mid': ['--varrenaming', '--garbagecode', '--compressor', '--wrapaliases'],
    'max': ['--varrenaming', '--garbagecode', '--compressor', '--wrapaliases', '--encaliases', '--vm'],
    'safe': ['--varrenaming', '--garbagecode'],
    'vm': ['--varrenaming', '--garbagecode', '--vm'],
}

async def run_obfuscator(code, preset='mid', custom_flags=None):
    req_id = str(uuid.uuid4())
    input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
    
    try:
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        with open(input_file, 'w') as f:
            f.write(code)
        
        # Build command with individual flags instead of preset
        cmd = ['lua', 'hercules.lua', input_file]
        
        if custom_flags:
            cmd.extend(custom_flags)
        elif preset in PRESETS:
            cmd.extend(PRESETS[preset])
        else:
            cmd.extend(PRESETS['mid'])
        
        print(f"Running: {' '.join(cmd)}")
        
        start = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=Config.HERCULES_PATH,
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=Config.OBFUSCATION_TIMEOUT)
        elapsed = time.time() - start
        
        stdout_text = stdout.decode() if stdout else ''
        stderr_text = stderr.decode() if stderr else ''
        
        print(f"STDOUT: {stdout_text[:500]}")
        print(f"STDERR: {stderr_text[:500]}")
        
        # Find output file
        output_file = None
        possible_outputs = [
            input_file.replace('.lua', '_obfuscated.lua'),
            os.path.join(Config.HERCULES_PATH, f'{req_id}_obfuscated.lua'),
            os.path.join(Config.HERCULES_PATH, os.path.basename(input_file).replace('.lua', '_obfuscated.lua')),
            os.path.join(os.path.dirname(input_file), f'{req_id}_obfuscated.lua'),
        ]
        
        # Also check current working directory
        for f in os.listdir(Config.HERCULES_PATH):
            if f.endswith('_obfuscated.lua') and req_id in f:
                possible_outputs.append(os.path.join(Config.HERCULES_PATH, f))
        
        for p in possible_outputs:
            if os.path.exists(p):
                output_file = p
                break
        
        if output_file:
            with open(output_file, 'r') as f:
                output = f.read()
            return {
                'success': True, 
                'output': output, 
                'time': f'{elapsed:.2f}s', 
                'original': len(code), 
                'obfuscated': len(output)
            }
        else:
            error_msg = stderr_text or stdout_text or 'No output file generated'
            return {'success': False, 'error': error_msg[:500]}
            
    except asyncio.TimeoutError:
        return {'success': False, 'error': 'Timeout (5 min limit)'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        # Cleanup
        cleanup_files = [
            input_file,
            input_file.replace('.lua', '_obfuscated.lua'),
        ]
        for f in cleanup_files:
            if os.path.exists(f):
                try: 
                    os.remove(f)
                except: 
                    pass

# ============ SLASH COMMANDS ============

@bot.tree.command(name="obfuscate", description="Obfuscate Lua code")
@app_commands.describe(
    code="Lua code to obfuscate",
    preset="Obfuscation level",
    file="Upload .lua file"
)
@app_commands.choices(preset=[
    app_commands.Choice(name="Safe - Basic (most stable)", value="safe"),
    app_commands.Choice(name="Minimum - Light", value="min"),
    app_commands.Choice(name="Medium - Balanced", value="mid"),
    app_commands.Choice(name="Maximum - Heavy", value="max"),
    app_commands.Choice(name="VM - Virtual Machine", value="vm"),
])
async def slash_obf(interaction: discord.Interaction, code: str = None, preset: str = "safe", file: discord.Attachment = None):
    on_cd, rem = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(embed=create_embed("⏳ Cooldown", f"Wait {rem}s", 0xffc800), ephemeral=True)
        return
    
    await interaction.response.defer()
    
    if file:
        content, err = await download_attachment(file)
        if err:
            await interaction.followup.send(embed=create_embed("❌ Error", err, 0xff6464))
            return
        code = content
    
    if not code:
        await interaction.followup.send(embed=create_embed("❌ Error", "Provide code or upload a file", 0xff6464))
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(embed=create_embed("🔄 Obfuscating", f"**Preset:** `{preset}`\nPlease wait...", 0xffc800))
    
    result = await run_obfuscator(code, preset)
    
    if result['success']:
        bot.stats['success'] += 1
        inc = ((result['obfuscated'] - result['original']) / result['original'] * 100) if result['original'] > 0 else 0
        
        embed = create_embed(
            "✅ Obfuscation Complete",
            f"**Preset:** `{preset}`\n**Time:** `{result['time']}`\n**Size:** `{result['original']:,}` → `{result['obfuscated']:,}` bytes (+{inc:.1f}%)",
            0x00ff64
        )
        
        await msg.edit(embed=embed)
        await interaction.followup.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.tree.command(name="obfuscate-custom", description="Obfuscate with custom modules")
@app_commands.describe(
    file="Upload .lua file",
    varrenaming="Variable renaming",
    garbagecode="Garbage code insertion",
    compressor="Compress output",
    vm="Virtual Machine protection",
    antitamper="Anti-tamper protection"
)
async def slash_custom(
    interaction: discord.Interaction,
    file: discord.Attachment,
    varrenaming: bool = True,
    garbagecode: bool = True,
    compressor: bool = False,
    vm: bool = False,
    antitamper: bool = False
):
    on_cd, rem = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(embed=create_embed("⏳", f"Wait {rem}s", 0xffc800), ephemeral=True)
        return
    
    await interaction.response.defer()
    
    content, err = await download_attachment(file)
    if err:
        await interaction.followup.send(embed=create_embed("❌", err, 0xff6464))
        return
    
    # Build custom flags
    flags = []
    if varrenaming:
        flags.append('--varrenaming')
    if garbagecode:
        flags.append('--garbagecode')
    if compressor:
        flags.append('--compressor')
    if vm:
        flags.append('--vm')
    if antitamper:
        flags.append('--antitamper')
    
    if not flags:
        flags = ['--varrenaming']  # At least one module
    
    bot.stats['total'] += 1
    
    enabled = ", ".join([f.replace('--', '') for f in flags])
    msg = await interaction.followup.send(embed=create_embed("🔄 Custom Obfuscation", f"**Modules:** {enabled}", 0xffc800))
    
    result = await run_obfuscator(content, custom_flags=flags)
    
    if result['success']:
        bot.stats['success'] += 1
        embed = create_embed(
            "✅ Complete",
            f"**Modules:** {enabled}\n**Time:** `{result['time']}`\n**Size:** `{result['original']:,}` → `{result['obfuscated']:,}`",
            0x00ff64
        )
        await msg.edit(embed=embed)
        await interaction.followup.send(file=discord.File(io.BytesIO(result['output'].encode()), filename=f"custom_{file.filename}"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌", result['error'][:500], 0xff6464))


@bot.tree.command(name="help", description="Show help")
async def slash_help(interaction: discord.Interaction):
    embed = create_embed("🛡️ Hercules Obfuscator", "Lua Code Obfuscation Tool")
    
    embed.add_field(
        name="📝 Commands",
        value="""
`/obfuscate` - Obfuscate with presets
`/obfuscate-custom` - Custom module selection
`/modules` - List available modules
`/stats` - View statistics
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚡ Presets",
        value="""
`safe` - Variable Renaming + Garbage Code (stable)
`min` - Same as safe
`mid` - + Compressor, Wrap Aliases
`max` - + VM, Enc Aliases
`vm` - Variable Renaming + VM
        """,
        inline=False
    )
    
    embed.add_field(
        name="💬 Quick Commands",
        value="`!obf <code>` - Quick obfuscate with safe preset",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Note",
        value="Use `safe` preset if other presets cause errors. Some modules may conflict with certain Lua code.",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="modules", description="List available modules")
async def slash_modules(interaction: discord.Interaction):
    embed = create_embed("🔧 Available Modules", "")
    
    modules_info = """
✅ **Stable Modules:**
• `varrenaming` - Rename variables to random names
• `garbagecode` - Insert fake/dead code
• `compressor` - Compress the output

⚠️ **May Cause Issues:**
• `controlflow` - Control flow obfuscation
• `stringencoding` - Encode strings
• `opaquepredicates` - Add confusing conditions

🔒 **Advanced:**
• `vm` - Virtual Machine protection
• `antitamper` - Tamper detection
• `wrapaliases` - Wrap function aliases
• `encaliases` - Encode aliases
    """
    
    embed.description = modules_info
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stats", description="View statistics")
async def slash_stats(interaction: discord.Interaction):
    up = datetime.utcnow() - bot.start_time
    h, r = divmod(int(up.total_seconds()), 3600)
    m, s = divmod(r, 60)
    d, h = divmod(h, 24)
    uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m {s}s"
    
    rate = (bot.stats['success'] / bot.stats['total'] * 100) if bot.stats['total'] > 0 else 0
    
    embed = create_embed("📊 Statistics", "")
    embed.add_field(name="Total", value=f"`{bot.stats['total']}`", inline=True)
    embed.add_field(name="Success", value=f"`{bot.stats['success']}`", inline=True)
    embed.add_field(name="Failed", value=f"`{bot.stats['failed']}`", inline=True)
    embed.add_field(name="Rate", value=f"`{rate:.1f}%`", inline=True)
    embed.add_field(name="Servers", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="Uptime", value=f"`{uptime}`", inline=True)
    
    await interaction.response.send_message(embed=embed)


# ============ PREFIX COMMANDS ============

@bot.command(name='obf')
async def cmd_obf(ctx, *, code: str = None):
    if ctx.message.attachments:
        content, err = await download_attachment(ctx.message.attachments[0])
        if err:
            await ctx.send(embed=create_embed("❌", err, 0xff6464))
            return
        code = content
    
    if not code:
        await ctx.send(embed=create_embed("❌ Error", "Usage: `!obf <code>` or attach a file", 0xff6464))
        return
    
    on_cd, rem = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳", f"Wait {rem}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 Obfuscating", "Using safe preset...", 0xffc800))
    
    result = await run_obfuscator(code, 'safe')
    
    if result['success']:
        bot.stats['success'] += 1
        await msg.edit(embed=create_embed("✅ Complete", f"**Time:** `{result['time']}`\n**Size:** `{result['original']:,}` → `{result['obfuscated']:,}`", 0x00ff64))
        await ctx.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.command(name='obf-vm')
async def cmd_vm(ctx):
    if not ctx.message.attachments:
        await ctx.send(embed=create_embed("❌", "Attach a .lua file", 0xff6464))
        return
    
    content, err = await download_attachment(ctx.message.attachments[0])
    if err:
        await ctx.send(embed=create_embed("❌", err, 0xff6464))
        return
    
    on_cd, rem = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳", f"Wait {rem}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄 VM Obfuscation", "Applying VM protection...", 0xffc800))
    
    result = await run_obfuscator(content, 'vm')
    
    if result['success']:
        bot.stats['success'] += 1
        await msg.edit(embed=create_embed("✅ Complete", f"Size: `{result['original']:,}` → `{result['obfuscated']:,}`", 0x00ff64))
        await ctx.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="vm_obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))


@bot.command(name='help')
async def cmd_help(ctx):
    embed = create_embed("🛡️ Hercules", "")
    embed.add_field(name="Commands", value="`/obfuscate` - Main command\n`!obf <code>` - Quick\n`!obf-vm` - With VM (attach file)", inline=False)
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(embed=create_embed("❌", str(error)[:200], 0xff6464))


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    try:
        msg = str(error)[:200]
        if interaction.response.is_done():
            await interaction.followup.send(embed=create_embed("❌", msg, 0xff6464), ephemeral=True)
        else:
            await interaction.response.send_message(embed=create_embed("❌", msg, 0xff6464), ephemeral=True)
    except:
        pass


if __name__ == '__main__':
    if not Config.DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        exit(1)
    print("Starting Hercules Obfuscator Bot...")
    bot.run(Config.DISCORD_TOKEN)
