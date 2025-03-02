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
    return "I'm alive! "

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
    """Fetches party compositions from Google Sheets and validates row data."""
    global roles
    roles = {}
    worksheets = sheet.worksheets()

    for ws in worksheets:
        party_type = ws.title.lower()
        roles[party_type] = {}
        data = ws.get_all_values()

        for row in data[1:]:  # Skip headers
            if len(row) < 3:  # Check if the row has at least 3 columns
                logging.warning(f"Skipping invalid row in Google Sheet (Not enough columns): {row}")
                continue

            try:
                role_number = int(row[0].strip())  # Convert role number to integer
                role_name = row[1].strip()
                category = row[2].strip()

                if category not in roles[party_type]:
                    roles[party_type][category] = {}
                roles[party_type][category][role_number] = role_name

            except ValueError:
                logging.warning(f"Skipping invalid row in Google Sheet (Invalid number format): {row}")

    logging.info("Roles loaded from Google Sheets.")


# Tracking Sheet Setup
tracking_sheet_name = "Signup Tracking"
try:
    tracking_sheet = sheet.worksheet(tracking_sheet_name)
except gspread.exceptions.WorksheetNotFound:
    tracking_sheet = sheet.add_worksheet(title=tracking_sheet_name, rows="100", cols="2")
    tracking_sheet.update("A1", [["User ID", "Signups"]])

def update_signup_count(user_id):
    """Updates the signup count for a user in the Google Sheet."""
    records = tracking_sheet.get_all_records()
    user_found = False
    for i, record in enumerate(records, start=2):
        if str(record["User ID"]) == str(user_id):
            new_count = int(record["Signups"]) + 1
            tracking_sheet.update(f"B{i}", new_count)
            user_found = True
            break
    if not user_found:
        tracking_sheet.append_row([str(user_id), "1"])

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
async def list_parties(ctx):
    """Lists all available party types."""
    available_parties = ', '.join(roles.keys())
    await ctx.send(f"**Available Party Types:** {available_parties}")

@bot.command()
async def albionbothelp(ctx):
    """Displays available commands."""
    help_message = (
        "**Albion Bot Commands:**\n"
        "!start <party_type> - Starts a new party signup.\n"
        "!refresh_roles - Refreshes roles from Google Sheets.\n"
        "!albionbothelp - Displays this help message."
    )
    await ctx.send(help_message)

@bot.command()
async def check_signups(ctx, user: discord.Member = None):
    """Checks the number of signups a user has."""
    user = user or ctx.author
    records = tracking_sheet.get_all_records()
    for record in records:
        if str(record["User ID"]) == str(user.id):
            await ctx.send(f"{user.mention} has signed up {record['Signups']} times.")
            return
    await ctx.send(f"{user.mention} has not signed up yet.")

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
    message = await ctx.send(f"Initializing {party_type.capitalize()} party signup...")
    await display_party_list(ctx.guild.id, party_type)
    thread = await ctx.channel.create_thread(name=f"Albion Online {party_type.capitalize()} Signup", type=discord.ChannelType.public_thread)
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

                    # Assign the user to the role slot
                    party["slots"][number] = message.author

                    # Log the signup to Google Sheets (ONLY if it's their first signup)
                    await log_signup_to_sheets(message.author.id, party_type)

                    # Find which category contains this role number
                    role_name = "Unknown Role"
                    for category, role_dict in party["roles"].items():
                        if number in role_dict:
                            role_name = role_dict[number]
                            break

                    await message.channel.send(f"{message.author.mention} signed up as {role_name}!")
                    await display_party_list(guild_id, party_type)
            except ValueError:
                await message.channel.send(f"{message.author.mention} invalid input. Enter a number to sign up or `-` to remove yourself.")

async def log_signup_to_sheets(user_id, party_type):
    """Logs a user's signup in the Google Sheet, ensuring only one signup per event."""
    try:
        # Fetch user details (optimize caching)
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        username = user.name if user else f"Unknown({user_id})"

        tracking_sheet = sheet.worksheet("Signup Tracking")
        data = tracking_sheet.get_all_values()

        # Ensure headers exist and include "User"
        headers = data[0] if data else ["User"]

        # If party type isn't listed, add it as a new column
        if party_type not in headers:
            headers.append(party_type)
            tracking_sheet.update("A1", [headers])  # Update headers immediately

        # Convert data into a dictionary for quick lookup
        existing_users = {row[0]: row[1:] for row in data[1:] if row}

        # Find the column index for the new party type
        party_col_index = headers.index(party_type)

        # Prepare data to update
        updated_data = []
        user_exists = False

        for uname, signups in existing_users.items():
            # Ensure all rows match header length
            while len(signups) < len(headers) - 1:
                signups.append("0")

            # If user exists, only mark first signup for this event
            if uname == username:
                user_exists = True
                if signups[party_col_index - 1] == "0":  # If first signup
                    signups[party_col_index - 1] = "1"
            updated_data.append([uname] + signups)

        # If user is new, add them to tracking
        if not user_exists:
            new_user_row = ["0"] * (len(headers) - 1)
            new_user_row[party_col_index - 1] = "1"
            updated_data.append([username] + new_user_row)

        # Only update necessary rows
        tracking_sheet.update(f"A2", updated_data)

        logging.info(f"Logged signup for {username} (ID: {user_id}) in {party_type}")

    except Exception as e:
        logging.error(f"Error logging signup: {e}")


if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)