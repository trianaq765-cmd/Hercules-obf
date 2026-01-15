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

async def run_obfuscator(code, preset='mid'):
    req_id = str(uuid.uuid4())
    input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
    
    try:
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        with open(input_file, 'w') as f:
            f.write(code)
        
        # Use lua (5.4)
        cmd = ['lua', 'hercules.lua', input_file, f'--{preset}']
        
        start = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=Config.HERCULES_PATH,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=Config.OBFUSCATION_TIMEOUT)
        elapsed = time.time() - start
        
        # Find output
        output_file = None
        for p in [input_file.replace('.lua', '_obfuscated.lua'),
                  os.path.join(Config.HERCULES_PATH, f'{req_id}_obfuscated.lua'),
                  os.path.join(Config.HERCULES_PATH, os.path.basename(input_file).replace('.lua', '_obfuscated.lua'))]:
            if os.path.exists(p):
                output_file = p
                break
        
        if output_file:
            with open(output_file, 'r') as f:
                output = f.read()
            return {'success': True, 'output': output, 'time': f'{elapsed:.2f}s', 'original': len(code), 'obfuscated': len(output)}
        return {'success': False, 'error': (stderr.decode() if stderr else stdout.decode() if stdout else 'Failed')[:300]}
    except asyncio.TimeoutError:
        return {'success': False, 'error': 'Timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        for f in [input_file, input_file.replace('.lua', '_obfuscated.lua')]:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

@bot.tree.command(name="obfuscate", description="Obfuscate Lua code")
@app_commands.describe(code="Lua code", preset="Level", file="Upload file")
@app_commands.choices(preset=[
    app_commands.Choice(name="Minimum", value="min"),
    app_commands.Choice(name="Medium", value="mid"),
    app_commands.Choice(name="Maximum", value="max"),
])
async def slash_obf(interaction: discord.Interaction, code: str = None, preset: str = "mid", file: discord.Attachment = None):
    on_cd, rem = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(embed=create_embed("⏳", f"Wait {rem}s", 0xffc800), ephemeral=True)
        return
    await interaction.response.defer()
    
    if file:
        content, err = await download_attachment(file)
        if err:
            await interaction.followup.send(embed=create_embed("❌", err, 0xff6464))
            return
        code = content
    
    if not code:
        await interaction.followup.send(embed=create_embed("❌", "Provide code or file", 0xff6464))
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(embed=create_embed("🔄", f"Preset: `{preset}`", 0xffc800))
    
    result = await run_obfuscator(code, preset)
    
    if result['success']:
        bot.stats['success'] += 1
        inc = ((result['obfuscated']-result['original'])/result['original']*100) if result['original']>0 else 0
        embed = create_embed("✅ Complete", f"**Time:** `{result['time']}`\n**Size:** `{result['original']:,}` → `{result['obfuscated']:,}` (+{inc:.1f}%)", 0x00ff64)
        await msg.edit(embed=embed)
        await interaction.followup.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌", result['error'][:400], 0xff6464))

@bot.tree.command(name="obfuscate-max", description="Maximum obfuscation")
@app_commands.describe(file="Upload .lua file")
async def slash_max(interaction: discord.Interaction, file: discord.Attachment):
    on_cd, rem = check_cooldown(interaction.user.id)
    if on_cd:
        await interaction.response.send_message(embed=create_embed("⏳", f"Wait {rem}s", 0xffc800), ephemeral=True)
        return
    await interaction.response.defer()
    
    content, err = await download_attachment(file)
    if err:
        await interaction.followup.send(embed=create_embed("❌", err, 0xff6464))
        return
    
    bot.stats['total'] += 1
    msg = await interaction.followup.send(embed=create_embed("🔄", "Max obfuscation...", 0xffc800))
    
    result = await run_obfuscator(content, 'max')
    
    if result['success']:
        bot.stats['success'] += 1
        await msg.edit(embed=create_embed("✅", f"Size: `{result['original']:,}` → `{result['obfuscated']:,}`", 0x00ff64))
        await interaction.followup.send(file=discord.File(io.BytesIO(result['output'].encode()), filename=f"max_{file.filename}"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌", result['error'][:400], 0xff6464))

@bot.tree.command(name="help", description="Help")
async def slash_help(interaction: discord.Interaction):
    embed = create_embed("🛡️ Hercules", "Lua Obfuscator")
    embed.add_field(name="Commands", value="`/obfuscate` - Obfuscate\n`/obfuscate-max` - Max protection\n`!obf <code>` - Quick", inline=False)
    embed.add_field(name="Presets", value="`min` `mid` `max`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="Statistics")
async def slash_stats(interaction: discord.Interaction):
    up = datetime.utcnow() - bot.start_time
    h, r = divmod(int(up.total_seconds()), 3600)
    m, s = divmod(r, 60)
    embed = create_embed("📊 Stats", "")
    embed.add_field(name="Total", value=f"`{bot.stats['total']}`", inline=True)
    embed.add_field(name="Success", value=f"`{bot.stats['success']}`", inline=True)
    embed.add_field(name="Servers", value=f"`{len(bot.guilds)}`", inline=True)
    await interaction.response.send_message(embed=embed)

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
    msg = await ctx.send(embed=create_embed("🔄", "Processing...", 0xffc800))
    result = await run_obfuscator(code)
    if result['success']:
        bot.stats['success'] += 1
        await msg.edit(embed=create_embed("✅", f"Time: `{result['time']}`", 0x00ff64))
        await ctx.send(file=discord.File(io.BytesIO(result['output'].encode()), filename="obfuscated.lua"))
    else:
        bot.stats['failed'] += 1
        await msg.edit(embed=create_embed("❌", result['error'][:300], 0xff6464))

@bot.command(name='help')
async def cmd_help(ctx):
    await ctx.send(embed=create_embed("🛡️", "`/obfuscate` or `!obf <code>`"))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return

if __name__ == '__main__':
    if not Config.DISCORD_TOKEN:
        print("ERROR: No token!")
        exit(1)
    bot.run(Config.DISCORD_TOKEN)
