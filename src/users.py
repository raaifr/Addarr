from telegram.ext import ConversationHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

import logging
import logger

from definitions import ADMIN_PATH, CHATID_PATH, ALLOWLIST_PATH
from commons import authentication, checkAllowed, checkId, format_long_list_message, getService, clearUserData, getChatName
from config import config
from translations import i18n
import radarr as radarr
import sonarr as sonarr

# Set up logging
logLevel = logging.DEBUG if config.get("debugLogging", False) else logging.INFO
logger = logger.getLogger("addarr.users", logLevel, config.get("logToConsole", False))

GIVE_USER_OPS, GET_USER_ID, REVOKE_USER = range(3)

async def startUserOps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # check and authenticate user
    if config.get("enableAllowlist") and not checkAllowed(update,"regular"):
        #When using this mode, bot will remain silent if user is not in the allowlist.txt
        logger.info("Allowlist is enabled, but userID isn't added into 'allowlist.txt'. So bot stays silent")
        return ConversationHandler.END

    if not checkAllowed(update, "admin") and config.get("enableAdmin"):
        await context.bot.send_message(
            chat_id=update.effective_message.chat_id,
            text=i18n.t("addarr.Authorization.NotAdmin"),
        )
        return ConversationHandler.END
    
    # prompt for user operation selection
    context.user_data["userops"] = ""
    keyboard = [
        [
            InlineKeyboardButton(
                i18n.t("addarr.Users.RevokeUser"),
                callback_data=i18n.t("addarr.Users.RevokeUser")
            ),
            InlineKeyboardButton(
                i18n.t("addarr.Users.ListUsers"),
                callback_data=i18n.t("addarr.Users.ListUsers")
            ),
        ],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    if not config.get("update_msg"):
        msg = await context.bot.send_message(
            chat_id=update.effective_message.chat_id, 
            text=i18n.t("addarr.Users.SelectUserOperation"),
            reply_markup=markup,
        )
        context.user_data["update_msg"] = msg.message_id
    else: 
        await context.bot.edit_message_text(
            message_id=context.user_data["update_msg"],
            chat_id=update.effective_message.chat_id,
            text=i18n.t("addarr.Users.SelectUserOperation"),
            reply_markup=markup,
        )
    
    return GIVE_USER_OPS

async def getUserID(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        reply = update.message.text.lower()
    elif update.callback_query is not None:
        reply = update.callback_query.data.lower()
        await update.callback_query.answer()
    else:
        return GIVE_USER_OPS
    
    # store selected operation
    context.user_data['user_operation'] = reply
    
    if reply.lower() == i18n.t("addarr.Users.ListUsers").lower():
        # If showing all users, we don't need a user ID
        return await showAllUsers(update, context)
    else:
        await update.callback_query.edit_message_text(
            text=i18n.t("addarr.Users.EnterUserID")
        )
        return GET_USER_ID
    

async def execUserOps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        reply = update.message.text.lower()
    elif update.callback_query is not None:
        reply = update.callback_query.data.lower()
        await update.callback_query.answer()
    else:
        return GIVE_USER_OPS

    if context.user_data.get("user_operation") is None:
        return startUserOps(update, context)
    
    ops = context.user_data['user_operation']
    userid = reply

    if ops == i18n.t("addarr.Users.AddUser"):
        with open(CHATID_PATH, "a") as file:
            name = await getChatName(context, userid)
            file.write(name)
            await context.bot.send_message(
                chat_id=update.effective_message.chat_id,
                text=i18n.t("addarr.Authorization.User_Added", username=name)
            )
            file.close()
            return "added"
    

async def showAllUsers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Read entries from file
        with open(CHATID_PATH, 'r', encoding='utf-8') as file:
            entries = [line.strip() for line in file if line.strip()]
            
        if not entries:
            await update.callback_query.edit_message_text(
                text="No entries found in the file."
            )
            return

        formatted_entries = []
        for i, entry in enumerate(entries, 1):
            if ' - ' in entry:
                user_id, username = entry.split(' - ', 1)
                formatted_entries.append(f"{i}. {username} - <i>{user_id}</i>")
            else:
                formatted_entries.append(f"{i}. {entry}")
                
        message_text = f"\U0001F4CB {i18n.t("addarr.Users.UserListHeader")}\n\n" + "\n".join(formatted_entries)
        
        await update.callback_query.edit_message_text(
            text=message_text,
            parse_mode=ParseMode.HTML
        )
        
    except FileNotFoundError:
        logger.error("The chatid file was not found")
        await update.callback_query.edit_message_text(
            text="\U0000274C Error: The data file was not found."
        )
    except Exception as e:
        logger.error("error reading the chatid file")
        await update.callback_query.edit_message_text(
            text=f"\U0000274C Error reading entries: {str(e)}"
        )
    finally:
        return ConversationHandler.END