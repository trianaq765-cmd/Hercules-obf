import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import uuid
import io
import time
import re
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
        self.debug_mode = True  # Enable debug by default
    
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

def clean_ansi(text):
    """Remove ANSI color codes from text"""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

async def run_obfuscator(code, preset='min', skip_verify=False, debug=False):
    """
    Run Hercules obfuscator with multiple fallback options
    """
    req_id = str(uuid.uuid4())[:8]
    input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
    debug_info = []
    
    try:
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        
        # Write input file
        with open(input_file, 'w') as f:
            f.write(code)
        
        debug_info.append(f"📁 Input file: {input_file}")
        debug_info.append(f"📏 Code size: {len(code)} bytes")
        
        # Try different command variations
        commands_to_try = [
            ['lua', 'hercules.lua', input_file, f'--{preset}'],
            ['lua', 'hercules.lua', input_file],  # No preset
            ['lua5.4', 'hercules.lua', input_file, f'--{preset}'],
        ]
        
        result_data = None
        last_error = None
        
        for cmd in commands_to_try:
            debug_info.append(f"\n🔧 Trying: {' '.join(cmd)}")
            
            try:
                start = time.time()
                proc = await asyncio.create_subprocess_exec(
                    *cmd, 
                    cwd=Config.HERCULES_PATH,
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                elapsed = time.time() - start
                
                stdout_text = clean_ansi(stdout.decode() if stdout else '')
                stderr_text = clean_ansi(stderr.decode() if stderr else '')
                
                debug_info.append(f"⏱️ Time: {elapsed:.2f}s")
                debug_info.append(f"📤 Exit code: {proc.returncode}")
                
                if stdout_text:
                    debug_info.append(f"📝 STDOUT:\n{stdout_text[:300]}")
                if stderr_text:
                    debug_info.append(f"⚠️ STDERR:\n{stderr_text[:300]}")
                
                # Search for output file
                output_file = await find_output_file(req_id, input_file, debug_info)
                
                if output_file:
                    with open(output_file, 'r') as f:
                        output = f.read()
                    
                    debug_info.append(f"✅ Output found: {output_file}")
                    debug_info.append(f"📏 Output size: {len(output)} bytes")
                    
                    result_data = {
                        'success': True,
                        'output': output,
                        'time': f'{elapsed:.2f}s',
                        'original': len(code),
                        'obfuscated': len(output),
                        'debug': '\n'.join(debug_info) if debug else None,
                        'command': ' '.join(cmd)
                    }
                    
                    # Cleanup output file
                    try:
                        os.remove(output_file)
                    except:
                        pass
                    
                    break  # Success, exit loop
                else:
                    last_error = stderr_text or stdout_text or 'No output file'
                    debug_info.append(f"❌ No output file found")
                    
            except asyncio.TimeoutError:
                debug_info.append("❌ Command timeout")
                last_error = "Timeout"
            except Exception as e:
                debug_info.append(f"❌ Error: {str(e)}")
                last_error = str(e)
        
        if result_data:
            return result_data
        else:
            return {
                'success': False,
                'error': last_error[:500] if last_error else 'Obfuscation failed',
                'debug': '\n'.join(debug_info) if debug else None
            }
            
    except Exception as e:
        debug_info.append(f"❌ Exception: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'debug': '\n'.join(debug_info) if debug else None
        }
    finally:
        # Cleanup input file
        if os.path.exists(input_file):
            try:
                os.remove(input_file)
            except:
                pass

async def find_output_file(req_id, input_file, debug_info):
    """Search for the obfuscated output file"""
    base_name = os.path.basename(input_file).replace('.lua', '_obfuscated.lua')
    
    # Possible locations
    locations = [
        input_file.replace('.lua', '_obfuscated.lua'),
        os.path.join(Config.HERCULES_PATH, base_name),
        os.path.join(Config.HERCULES_PATH, f'{req_id}_obfuscated.lua'),
        os.path.join(Config.UPLOAD_FOLDER, base_name),
    ]
    
    # Also scan directories for any obfuscated files
    for directory in [Config.HERCULES_PATH, Config.UPLOAD_FOLDER]:
        try:
            for f in os.listdir(directory):
                if '_obfuscated.lua' in f:
                    full_path = os.path.join(directory, f)
                    locations.append(full_path)
                    debug_info.append(f"🔍 Found file: {f}")
        except:
            pass
    
    # Check each location
    for loc in locations:
        if os.path.exists(loc):
            return loc
    
    return None

async def test_hercules():
    """Test if Hercules is working"""
    debug_info = []
    
    # Test 1: Check if lua is available
    try:
        proc = await asyncio.create_subprocess_exec(
            'lua', '-v',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        lua_version = clean_ansi((stdout or stderr).decode())
        debug_info.append(f"✅ Lua: {lua_version.strip()}")
    except Exception as e:
        debug_info.append(f"❌ Lua not found: {e}")
    
    # Test 2: Check hercules directory
    try:
        files = os.listdir(Config.HERCULES_PATH)
        debug_info.append(f"✅ Hercules path: {Config.HERCULES_PATH}")
        debug_info.append(f"📁 Files: {', '.join(files[:10])}")
        if 'hercules.lua' in files:
            debug_info.append("✅ hercules.lua found")
        else:
            debug_info.append("❌ hercules.lua NOT found")
    except Exception as e:
        debug_info.append(f"❌ Cannot read hercules path: {e}")
    
    # Test 3: Run hercules help
    try:
        proc = await asyncio.create_subprocess_exec(
            'lua', 'hercules.lua', '--help',
            cwd=Config.HERCULES_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        output = clean_ansi((stdout or stderr).decode())
        debug_info.append(f"✅ Hercules help:\n{output[:500]}")
    except Exception as e:
        debug_info.append(f"❌ Hercules help failed: {e}")
    
    # Test 4: Simple obfuscation test
    test_code = 'print("test")'
    debug_info.append(f"\n🧪 Testing with: {test_code}")
    
    result = await run_obfuscator(test_code, 'min', debug=True)
    if result['success']:
        debug_info.append(f"✅ Test obfuscation SUCCESS")
        debug_info.append(f"📏 Output size: {result['obfuscated']} bytes")
    else:
        debug_info.append(f"❌ Test obfuscation FAILED: {result['error']}")
    
    if result.get('debug'):
        debug_info.append(f"\n📋 Debug output:\n{result['debug']}")
    
    return '\n'.join(debug_info)

# ============ SLASH COMMANDS ============

@bot.tree.command(name="obfuscate", description="Obfuscate Lua code")
@app_commands.describe(
    code="Lua code to obfuscate",
    preset="Obfuscation level",
    file="Upload .lua file",
    debug="Show debug information"
)
@app_commands.choices(preset=[
    app_commands.Choice(name="Minimum - Light", value="min"),
    app_commands.Choice(name="Medium - Balanced", value="mid"),
    app_commands.Choice(name="Maximum - Heavy", value="max"),
])
async def slash_obf(
    interaction: discord.Interaction, 
    code: str = None, 
    preset: str = "min", 
    file: discord.Attachment = None,
    debug: bool = False
):
    on_cd, rem = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(
            embed=create_embed("⏳ Cooldown", f"Wait {rem}s", 0xffc800), 
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    if file:
        content, err = await download_attachment(file)
        if err:
            await interaction.followup.send(embed=create_embed("❌ Error", err, 0xff6464))
            return
        code = content
    
    if not code:
        await interaction.followup.send(
            embed=create_embed("❌ Error", "Provide code or upload a file", 0xff6464)
        )
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(
        embed=create_embed("🔄 Obfuscating", f"**Preset:** `{preset}`\nPlease wait...", 0xffc800)
    )
    
    result = await run_obfuscator(code, preset, debug=debug)
    
    if result['success']:
        bot.stats['success'] += 1
        inc = ((result['obfuscated'] - result['original']) / result['original'] * 100) if result['original'] > 0 else 0
        
        embed = create_embed(
            "✅ Obfuscation Complete",
            f"**Preset:** `{preset}`\n**Time:** `{result['time']}`\n**Size:** `{result['original']:,}` → `{result['obfuscated']:,}` bytes (+{inc:.1f}%)",
            0x00ff64
        )
        
        await msg.edit(embed=embed)
        
        # Send output file
        await interaction.followup.send(
            file=discord.File(io.BytesIO(result['output'].encode()), filename="obfuscated.lua")
        )
        
        # Send debug info if requested
        if debug and result.get('debug'):
            debug_text = result['debug'][:1900]
            await interaction.followup.send(f"```\n{debug_text}\n```")
    else:
        bot.stats['failed'] += 1
        error_msg = result['error'][:500]
        
        embed = create_embed("❌ Failed", error_msg, 0xff6464)
        await msg.edit(embed=embed)
        
        # Always show debug on failure
        if result.get('debug'):
            debug_text = result['debug'][:1900]
            await interaction.followup.send(f"**Debug Info:**\n```\n{debug_text}\n```")


@bot.tree.command(name="test", description="Test if Hercules obfuscator is working")
async def slash_test(interaction: discord.Interaction):
    await interaction.response.defer()
    
    msg = await interaction.followup.send(
        embed=create_embed("🧪 Testing", "Running diagnostics...", 0xffc800)
    )
    
    test_result = await test_hercules()
    
    # Split into chunks if too long
    chunks = [test_result[i:i+1900] for i in range(0, len(test_result), 1900)]
    
    await msg.edit(embed=create_embed("🧪 Test Complete", "See results below", 0x00d4ff))
    
    for i, chunk in enumerate(chunks[:3]):  # Max 3 chunks
        await interaction.followup.send(f"```\n{chunk}\n```")


@bot.tree.command(name="debug", description="Toggle debug mode")
async def slash_debug(interaction: discord.Interaction):
    bot.debug_mode = not bot.debug_mode
    status = "enabled" if bot.debug_mode else "disabled"
    await interaction.response.send_message(
        embed=create_embed("🔧 Debug Mode", f"Debug mode is now **{status}**", 0x00d4ff)
    )


@bot.tree.command(name="help", description="Show help")
async def slash_help(interaction: discord.Interaction):
    embed = create_embed("🛡️ Hercules Obfuscator", "Lua Code Obfuscation Tool")
    
    embed.add_field(
        name="📝 Commands",
        value="""
`/obfuscate` - Obfuscate code (add `debug:True` for details)
`/test` - Test if Hercules is working
`/debug` - Toggle debug mode
`/stats` - View statistics
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚡ Presets",
        value="""
`min` - Light (most stable)
`mid` - Balanced
`max` - Heavy (may fail on some code)
        """,
        inline=False
    )
    
    embed.add_field(
        name="💬 Prefix Commands",
        value="""
`!obf <code>` - Quick obfuscate
`!test` - Quick test
`!debug` - Show debug info
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Troubleshooting",
        value="If obfuscation fails, try:\n1. Use `/test` to check status\n2. Use `min` preset\n3. Add `debug:True` to see details",
        inline=False
    )
    
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
    embed.add_field(name="Debug", value=f"`{'ON' if bot.debug_mode else 'OFF'}`", inline=True)
    
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
        await ctx.send(embed=create_embed("❌", "`!obf <code>` or attach file", 0xff6464))
        return
    
    on_cd, rem = check_cooldown(ctx.author.id)
    if on_cd:
        await ctx.send(embed=create_embed("⏳", f"Wait {rem}s", 0xffc800))
        return
    
    bot.stats['total'] += 1
    msg = await ctx.send(embed=create_embed("🔄", "Obfuscating...", 0xffc800))
    
    result = await run_obfuscator(code, 'min', debug=bot.debug_mode)
    
    if result['success']:
        bot.stats['success'] += 1
        await msg.edit(embed=create_embed(
            "✅ Complete", 
            f"Time: `{result['time']}`\nSize: `{result['original']:,}` → `{result['obfuscated']:,}`", 
            0x00ff64
        ))
        await ctx.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌ Failed", result['error'][:500], 0xff6464))
        if result.get('debug'):
            await ctx.send(f"```\n{result['debug'][:1500]}\n```")


@bot.command(name='test')
async def cmd_test(ctx):
    msg = await ctx.send(embed=create_embed("🧪", "Testing...", 0xffc800))
    test_result = await test_hercules()
    await msg.edit(embed=create_embed("🧪 Test Complete", "", 0x00d4ff))
    
    # Split and send
    for chunk in [test_result[i:i+1900] for i in range(0, len(test_result), 1900)][:2]:
        await ctx.send(f"```\n{chunk}\n```")


@bot.command(name='debug')
async def cmd_debug(ctx):
    """Show current debug info"""
    info = f"""
**Debug Info**
• Hercules Path: `{Config.HERCULES_PATH}`
• Upload Folder: `{Config.UPLOAD_FOLDER}`
• Debug Mode: `{'ON' if bot.debug_mode else 'OFF'}`
• Stats: {bot.stats}
    """
    await ctx.send(embed=create_embed("🔧 Debug", info, 0x00d4ff))


@bot.command(name='help')
async def cmd_help(ctx):
    embed = create_embed("🛡️ Hercules", "")
    embed.add_field(
        name="Commands", 
        value="`/obfuscate` - Main\n`/test` - Test\n`!obf <code>` - Quick\n`!test` - Quick test", 
        inline=False
    )
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(embed=create_embed("❌", str(error)[:200], 0xff6464))


if __name__ == '__main__':
    if not Config.DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        exit(1)
    
    # Print startup info
    print("=" * 50)
    print("Hercules Obfuscator Bot Starting...")
    print(f"Hercules Path: {Config.HERCULES_PATH}")
    print(f"Upload Folder: {Config.UPLOAD_FOLDER}")
    print("=" * 50)
    
    bot.run(Config.DISCORD_TOKEN)
