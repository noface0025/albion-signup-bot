import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from keep_alive import keep_alive
from flask import Flask
from threading import Thread

# Keep-Alive Server
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Load environment variables
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    print("ERROR: Bot token not found. Make sure it is set in Replit Secrets.")
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
    print("Bot is ready and listening for commands!")

@bot.command()
async def start(ctx, party_type: str):
    """Starts a new party based on the type given."""
    await create_party(ctx, party_type.lower())

async def create_party(ctx, party_type):
    """Helper function to create a new party and post the signup list."""
    if party_type not in roles:
        await ctx.send("Invalid party type. Available options: clap, brawl, 10")
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

async def display_party_list(guild_id, party_type):
    """Displays the current party list in the main channel."""
    if (guild_id, party_type) not in parties:
        return

    party = parties[(guild_id, party_type)]
    msg = f"**{party_type.capitalize()} Party List:**\n"

    for category, role_dict in party["roles"].items():
        msg += f"\n**{category}**\n"
        for num, role in role_dict.items():
            user = party["slots"].get(num)
            if user:
                msg += f"{num}: {role} - {user.mention}\n"
            else:
                msg += f"{num}: {role} - [Open Slot]\n"

    await party["main_message"].edit(content=msg)

if __name__ == "__main__":
    keep_alive()  # Start the keep-alive web server before running the bot
    bot.run(TOKEN)
