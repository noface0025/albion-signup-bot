import discord
import os
import subprocess
from discord.ext import commands
from dotenv import load_dotenv
from keep_alive import keep_alive

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    print("ERROR: Bot token not found. Make sure it is set in the .env file or Replit Secrets.")
    exit(1)

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

parties = {}  # Dictionary to track parties

roles = {
    "clap": {
        "Tank": {1: "Caller", 2: "1H Hammer", 3: "Heavy Mace", 4: "Heavy Mace", 5: "Bedrock"},
        "Support": {6: "Carving", 7: "Realm", 8: "Lifecurse", 9: "Oathkeeper", 10: "Enigmatic", 11: "Rootbound"},
        "DPS": {12: "Perma", 13: "Spiked", 14: "Spirit Hunter", 15: "Scythe", 16: "Sythe"},
        "Healer": {17: "Hallowfall", 18: "Hallowfall", 19: "Blight", 20: "Fallen"}
    },
    "brawl": {
        "Tank": {1: "Caller", 2: "Heavy Mace - Duskweave", 3: "Heavy Mace - Guardian", 4: "1H Hammer - Duskweave"},
        "Support": {5: "Oathkeeper - Demon", 6: "Enigmatic - Demon", 7: "Rootbound - Judi", 8: "Lifecurse - Demon", 9: "Occult - FULL CD (Assassin Hood, Royal Jacket)"},
        "Healer": {10: "Holy - Judi", 11: "Holy - Judi", 12: "Holy - Judi", 13: "Blight"},
        "DPS": {14: "DPS Scythe 1", 15: "DPS Scythe 2", 16: "DPS Scythe 3", 17: "DPS Scythe 4", 18: "DPS Cook 1", 19: "DPS Cook 2", 20: "DPS Cook 3"}
    },
    "10": {
        "Tank": {1: "Caller", 2: "Heavy Mace/Hammer"},
        "Support": {3: "Rootbound", 4: "Lifecurse"},
        "Healer": {5: "Healer 1 - Hallow/Redemption", 6: "Healer 2 - Blight"},
        "DPS": {7: "Perma", 8: "Spirit Hunter", 9: "Hellfire", 10: "Riftglaive/ Longbow"}
    }
}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

keep_alive()

# GitHub Deployment Commands
def deploy_to_github():
    try:
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Auto commit from bot"], check=True)
        subprocess.run(["git", "branch", "-M", "main"], check=True)
        subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/noface0025/albion-signup-bot.git"], check=True)
        subprocess.run(["git", "push", "-u", "origin", "main", "--force"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"GitHub deployment failed: {e}")

deploy_to_github()


async def create_party(ctx, party_type):
    """Helper function to create a new party and post the signup list."""
    if party_type not in roles:
        await ctx.send("Invalid party type. Available options: clap, brawl, skirmish")
        return

    role_set = roles[party_type]
    thread = await ctx.channel.create_thread(name=f"Albion Online {party_type.capitalize()} Signup", type=discord.ChannelType.public_thread)
    message = await ctx.send(f"Initializing {party_type.capitalize()} party signup...")
    parties[(ctx.guild.id, party_type)] = {
        "thread": thread,
        "slots": {},
        "main_message": message,
        "roles": role_set
    }

    for category, role_dict in role_set.items():
        for num, role in role_dict.items():
            parties[(ctx.guild.id, party_type)]["slots"][num] = None

    # Assign the party starter to the first role (Caller)
    parties[(ctx.guild.id, party_type)]["slots"][1] = ctx.author
    await ctx.send(f"@everyone {party_type.capitalize()} Party signup started! Type the number of the role you want in {thread.mention}. Only one person per role! Type '-' to remove yourself from the signup list before selecting a new role.")
    await display_party_list(ctx.guild.id, party_type)

bot.run(TOKEN)