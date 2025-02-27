import discord
import os
import time
import logging
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import psutil

# Setup logging
logging.basicConfig(level=logging.INFO)

# Keep-Alive Server
app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive! This is the correct URL to use in UptimeRobot."

def run():
    app.run(host="0.0.0.0", port=5000)  # Changed port to avoid conflicts

def keep_alive():
    for conn in psutil.net_connections():
        if conn.laddr.port == 5000:
            print("Keep-Alive Server is already running.")
            return
    t = Thread(target=run, daemon=True)
    t.start()
    print("Keep-Alive Server Running! Check your Replit logs for the public URL.")

# Load environment variables
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")

if not TOKEN:
    logging.error("ERROR: Bot token not found. Ensure it's set in Replit Secrets.")
    exit(1)

if not GOOGLE_CREDENTIALS:
    logging.error("ERROR: Google Sheets credentials not found. Ensure it's set in Replit Secrets.")
    exit(1)

# Convert JSON string back to dictionary
try:
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
except json.JSONDecodeError as e:
    logging.error(f"ERROR: Failed to decode Google credentials JSON: {e}")
    exit(1)

# Authenticate with Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)

# Debugging: Ensure the bot can access available spreadsheets
logging.info("Available Sheets: " + str([s.title for s in gc.openall()]))

try:
    sheet = gc.open(GOOGLE_SHEET_NAME)
    logging.info(f"Successfully connected to the Google Sheet: {GOOGLE_SHEET_NAME}")
except gspread.exceptions.SpreadsheetNotFound:
    logging.error(f"ERROR: Google Sheet '{GOOGLE_SHEET_NAME}' not found. Check the sheet name and sharing settings.")
    exit(1)

def load_roles_from_sheets():
    """Fetches party compositions from Google Sheets."""
    global roles
    roles = {}
    worksheets = sheet.worksheets()
    for ws in worksheets:
        party_type = ws.title.lower()
        roles[party_type] = {}
        data = ws.get_all_values()
        for row in data[1:]:
            try:
                role_number = int(row[0])  # Convert role number to integer
                role_name = row[1].strip()
                category = row[2].strip()

                if category not in roles[party_type]:
                    roles[party_type][category] = {}
                roles[party_type][category][role_number] = role_name
            except ValueError:
                logging.warning(f"Skipping invalid row in Google Sheet: {row}")
    logging.info("Roles loaded from Google Sheets.")

# Load roles from the Google Sheet
load_roles_from_sheets()

# Initialize Discord Bot
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

parties = {}  # Dictionary to track parties

@bot.event
async def on_ready():
    if bot.user:
        logging.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
        print(f'Logged in as {bot.user} (ID: {bot.user.id})')
        logging.info("Bot is ready and listening for commands!")
    else:
        logging.error("Bot login failed!")

@bot.command()
async def refresh_roles(ctx):
    """Manually refreshes the roles from Google Sheets."""
    load_roles_from_sheets()
    await ctx.send("Roles have been refreshed from Google Sheets!")

@bot.command()
async def start(ctx, party_type: str):
    """Starts a new party based on the type given."""
    await create_party(ctx, party_type.lower())

async def create_party(ctx, party_type):
    """Helper function to create a new party and post the signup list."""
    if party_type not in roles:
        await ctx.send(f"Invalid party type. Available options: {', '.join(roles.keys())}")
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

    # Assign the party starter to the first role
    first_role_number = min(role_set[list(role_set.keys())[0]].keys())
    parties[(ctx.guild.id, party_type)]["slots"][first_role_number] = ctx.author

    await ctx.send(f"@everyone {party_type.capitalize()} Party signup started! Type the number of the role you want in {thread.mention}. Only one person per role! Type '-' to remove yourself before selecting a new role.")
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

@bot.event
async def on_message(message):
    """Handles user sign-ups in the thread."""
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    for (guild_id, party_type), party in parties.items():
        if message.guild.id == guild_id and message.channel == party["thread"]:
            user_signed_up = any(user == message.author for user in party["slots"].values())

            if message.content.strip() == "-":
                for num, user in party["slots"].items():
                    if user == message.author:
                        party["slots"][num] = None
                        await message.channel.send(f"{message.author.mention} removed from the signup.")
                        await display_party_list(guild_id, party_type)
                        return
                await message.channel.send(f"{message.author.mention} you are not signed up for any role.")
                return

            try:
                number = int(message.content.strip())
                if number in party["slots"]:
                    if user_signed_up:
                        await message.channel.send(f"{message.author.mention} you are already signed up. Use `-` to remove yourself first.")
                        return
                    party["slots"][number] = message.author
                    await message.channel.send(f"{message.author.mention} signed up as {party['roles'][party_type].get(number, 'Unknown Role')}!")
                    await display_party_list(guild_id, party_type)
            except ValueError:
                await message.channel.send(f"{message.author.mention} invalid input. Enter a number to sign up or `-` to remove yourself.")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
