#import libraries
import settings as keys
from db_setup import database_initialisation
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, Application, ContextTypes
import datetime
from pprint import pprint
import requests
import sqlite3 # to retrieve chat history
import google.generativeai as genai
import google.ai.generativelanguage as glm
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import warnings
warnings.filterwarnings('ignore')

genai.configure(api_key=keys.GOOGLE_API_KEY)
model= genai.GenerativeModel('gemini-pro')
model_vision = genai.GenerativeModel('gemini-pro-vision')
# set safety parameters
safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
    }

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Ask Jimmy something!')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('If you need help! You should ask my creator!')

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await print(f"Update {update} caused error {context.error}")


def download_image(file_id):
  """This function retrieves the file set to the bot."""
  url = f"https://api.telegram.org/bot{keys.API_KEY}/getFile?file_id={file_id}"
  response = requests.get(url)
  file_info = response.json()
  file_url = f"https://api.telegram.org/file/bot{keys.API_KEY}/{file_info['result']['file_path']}"
  image_data = requests.get(file_url).content
  return image_data


### DATABASE FUNCTIONS ###
# Function to create the database connection
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(e)
    return conn

# Function to retrieve conversations for a particular user ID
def get_conversations_for_user(conn, user_id):
    sql = """
    SELECT *
    FROM chat_history
    WHERE user_id = ?
    """
    cur = conn.cursor()
    cur.execute(sql, (user_id,))
    rows = cur.fetchall()
    return rows

# Get the key information
def append_conversations_to_messages(new_message, conversations, max_convo):
    """
    new_message - dictionary for the input prompt
    conversations - output of get_conversations_for_user function
    Combining them together to take into consideration historical chat context.

    max_convo - Recall chat history up till the past 6 conversations. Must be even number.
    """
    messages = [] # create empty list

    if conversations:
        max_convo = max_convo # i want it to loop 4 times only
        loop_counter = 1 # start counting the loops. 
        # append historical messages to messages list

        if len(conversations) > max_convo:
            for content in conversations[-max_convo:]:
                if loop_counter <= max_convo:
                    convo = {}
                    convo['parts'] = [content[4]]
                    convo['role'] = content[3]
                    messages.append(convo)
                    loop_counter += 1
                else:
                    break # break out of the for loop
        else:
            for content in conversations:
                convo = {}
                convo['parts'] = [content[4]]
                convo['role'] = content[3]
                messages.append(convo)

    messages.append(new_message)

    return messages


# Function to add a new conversation to the database
def add_conversation(conn, user_id, timestamp, role, response):
    timestamp = datetime.datetime.now() #.strftime('%Y-%m-%d %H:%M:%S')
    sql_insert_conversation = """
    INSERT INTO chat_history (user_id, timestamp, role, parts)
    VALUES (?, ?, ?, ?)
    """
    try:
        c = conn.cursor()
        c.execute(sql_insert_conversation, (user_id, timestamp, role, response))
        conn.commit()
        print("New conversation added successfully.")
    except sqlite3.Error as e:
        print(e)


# path to the sqlite3 database
db_name =  keys.chat_history_db

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get the message text and photo (if available)
    message_username = update.message.from_user.username
    message_firstname = update.message.from_user.first_name
    message_text = update.message.text
    message_photo = update.message.photo
    effective_chat_id = update.effective_chat.id
    timestamp = datetime.datetime.now()
    error_response = "" # start as empty

    # 1. Load conversations for the specified user ID
    # Connect to the database
    conn = create_connection(db_name)
    if conn is None:
        print("Error: Unable to connect to the database")

    # Check if image is present
    if message_photo:
        # Get the file ID of the image
        file_id = message_photo[-1].file_id # this should be a list of dictionaries where the last item is the photo submitted.
        image_data = download_image(file_id)

        message_text = update.message.caption # retrieve the caption

        print(f'{timestamp} | {effective_chat_id} | {message_username}', ': ', str(message_text))
        if not message_text:
            # if no caption. then just prompt to describe the image
            message_text = "Describe the contents of this image."

        try:
            # Use gemini-pro-vision for combined input (caption and image_data)
            response = model_vision.generate_content(
                glm.Content(
                    parts = [
                        glm.Part(text=message_text),
                        glm.Part(
                            inline_data=glm.Blob(
                                mime_type='image/jpeg', # image/* can allow jpg or png images. for strictly jpg files use this -> image/jpeg
                                data=image_data
                            )
                        ),
                    ],
                ), safety_settings=safety_settings,
                stream=False)
            await context.bot.send_message(chat_id=effective_chat_id, text=response.text)
            model_timestamp = datetime.datetime.now()
            print(f'{model_timestamp} | reply', ': ', response.text)

        except Exception as e:
            # Handle errors from gemini-pro-vision
            model_timestamp = datetime.datetime.now()
            print(f"{model_timestamp} | Error using gemini-pro-vision: {e}")
            error_response = f"Sorry {message_firstname}, I am unable to give you a response."
            await context.bot.send_message(chat_id=effective_chat_id, text=error_response)
    else:
        # No image, use gemini-pro on text
        print(f'{timestamp} | {effective_chat_id} | {message_username}', ': ', str(message_text))
        try:
            # Store the latest message
            new_message = {'role':'user',
                         'parts': [message_text]}

            # retrieve previous convos
            # Retrieve conversations for a specific user ID
            conversations = get_conversations_for_user(conn, effective_chat_id)
            messages = append_conversations_to_messages(new_message, conversations, max_convo=6)
            pprint(messages)
            response = model.generate_content(messages, safety_settings=safety_settings)
            model_timestamp = datetime.datetime.now()
            await context.bot.send_message(chat_id=effective_chat_id, text=response.text)
            print(f'{model_timestamp} | reply to {effective_chat_id} | {message_username}', ': ', response.text)

        except Exception as e:
            # Handle errors from gemini-pro
            model_timestamp = datetime.datetime.now()
            print(f"{model_timestamp} | Error using gemini-pro: {e}")
            error_response = f"Sorry {message_firstname}, I am unable to give you a response."
            await context.bot.send_message(chat_id=effective_chat_id, text=error_response)

    # update the chat history

    # add the user message
    add_conversation(conn, effective_chat_id, timestamp, 'user', message_text)

    if error_response == "":
        # then add the model response
        add_conversation(conn, effective_chat_id, model_timestamp, 'model', response.text)

    else:
        # then add the model response
        add_conversation(conn, effective_chat_id, model_timestamp, 'model', error_response)

    # Close the database connection
    conn.close()



def main():
    """Run the bot."""
    application = Application.builder().token(keys.API_KEY).build()

    # add conversation handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(None, handle_message)) # Set to None so that it can receive images and text
    application.add_error_handler(error)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

### ACTIVATE! ###
if __name__ == "__main__":
    print(f"{datetime.datetime.now()} Bot is alive ...")
    database_initialisation() # resets the database
    main() # activates the bot on telegram

