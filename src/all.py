from telegram.ext import ConversationHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
import logging
import logger

from commons import authentication, checkAllowed, checkId, format_long_list_message, getService, clearUserData
from config import config
from translations import i18n
import radarr as radarr
import sonarr as sonarr

# Set up logging
logLevel = logging.DEBUG if config.get("debugLogging", False) else logging.INFO
logger = logger.getLogger("addarr.radarr", logLevel, config.get("logToConsole", False))

LS_GIVE_MOVIE_INSTANCE, LS_GIVE_SERIE_INSTANCE, GG_STATE = range(3)

async def startAllSeries(update, context):
    # check and authenticate user
    if config.get("enableAllowlist") and not checkAllowed(update,"regular"):
        #When using this mode, bot will remain silent if user is not in the allowlist.txt
        logger.info("Allowlist is enabled, but userID isn't added into 'allowlist.txt'. So bot stays silent")
        return ConversationHandler.END

    if not checkId(update):
        if (
            await authentication(update, context) == "added"
        ):  # To also stop the beginning command
            return ConversationHandler.END
    else:
        # prompt for sonarr instance selection
        context.user_data["choice"] = i18n.t("addarr.Series")
        await lsPromptInstanceSelection(update, context)
        return LS_GIVE_SERIE_INSTANCE
        

async def storeSerieInstance(update, context):
    if update.message is not None:
        reply = update.message.text.lower()
    elif update.callback_query is not None:
        reply = update.callback_query.data
    else:
        return LS_GIVE_SERIE_INSTANCE

    # store the selected instance
    if reply.startswith("instance="):
        label = reply.replace("instance=", "", 1)
    else:
        label = reply
    
    context.user_data["instance"] = label
    
    instance = context.user_data["instance"]
    service = getService(context)
    service.setInstance(instance)

    if service.config.get("adminRestrictions") and not checkAllowed(update,"admin"):
        await context.bot.send_message(
            chat_id=update.effective_message.chat_id,
            text=i18n.t("addarr.NotAdmin"),
        )
        return ConversationHandler.END

    msgid = context.user_data["update_msg"]
    await context.bot.edit_message_text(
            chat_id=update.effective_message.chat_id,
            message_id=msgid,
            text=i18n.t("addarr.Loading All"),
    )

    # show all series. 
    result = service.allSeries()
    content = format_long_list_message(result)
    
    if isinstance(content, str):
        await context.bot.send_message(
            chat_id=update.effective_message.chat_id,
            text=content,
        )
    else:
        for subString in content:
            await context.bot.send_message(
                chat_id=update.effective_message.chat_id,
                text=subString,
        )
    return ConversationHandler.END


async def startAllMovies(update, context):
    # check and authenticate user
    if config.get("enableAllowlist") and not checkAllowed(update,"regular"):
        # When using this mode, bot will remain silent if user is not in the allowlist.txt
        logger.info("Allowlist is enabled, but userID isn't added into 'allowlist.txt'. So bot stays silent")
        return ConversationHandler.END
    
    if not checkId(update):
        if (
            await authentication(update, context) == "added"
        ):  # To also stop the beginning command
            return ConversationHandler.END
    else:
        # prompt for sonarr instance selection
        context.user_data["choice"] = i18n.t("addarr.Movie")
        await lsPromptInstanceSelection(update, context)
        return LS_GIVE_MOVIE_INSTANCE
        

async def storeMovieInstance(update, context):
    if update.message is not None:
        reply = update.message.text.lower()
    elif update.callback_query is not None:
        reply = update.callback_query.data
    else:
        return LS_GIVE_MOVIE_INSTANCE

    # store the selected instance
    if reply.startswith("instance="):
        label = reply.replace("instance=", "", 1)
    else:
        label = reply

    logger.debug(reply)
    
    context.user_data["instance"] = label
    
    instance = context.user_data["instance"]
    service = getService(context)
    service.setInstance(instance)

    if service.config.get("adminRestrictions") and not checkAllowed(update,"admin"):
        await context.bot.send_message(
            chat_id=update.effective_message.chat_id,
            text=i18n.t("addarr.NotAdmin"),
        )
        return ConversationHandler.END

    msgid = context.user_data["update_msg"]
    await context.bot.edit_message_text(
            chat_id=update.effective_message.chat_id,
            message_id=msgid,
            text=i18n.t("addarr.Loading All"),
    )
    
    # show all movies. 
    result = service.all_movies()
    content = format_long_list_message(result)
    if isinstance(content, str):
        await context.bot.send_message(
            chat_id=update.effective_message.chat_id,
            text=content,
        )
    else:
        for subString in content:
            await context.bot.send_message(
                chat_id=update.effective_message.chat_id,
                text=subString,
        )
    return ConversationHandler.END

async def lsPromptInstanceSelection(update : Update, context):
    service_name = 'radarr' if context.user_data["choice"].lower() == i18n.t("addarr.Movie").lower() else 'sonarr'
    instances = config[service_name]["instances"] 
    if len(instances) == 1:
        # There is only 1 instance, so use it!
        logger.debug(f"Only found 1 instance of {service_name}, so proceeding with that one...")
        context.user_data["instance"] = instances[0]["label"]
        return # skip to next step
    keyboard = []
    for instance in instances:
        label = instance['label']
        keyboard += [[
            InlineKeyboardButton(
            label,
            callback_data=f"instance={label}"
            ),
        ]]
    markup = InlineKeyboardMarkup(keyboard)
    
    msg = await update.effective_chat.send_message(
        text=i18n.t("addarr.Select an instance"),
        reply_markup=markup
    )
    context.user_data["update_msg"] = msg.message_id
