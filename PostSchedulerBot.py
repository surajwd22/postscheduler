from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
import time
import aiohttp
import cloudinary
import cloudinary.uploader
import os
import datetime

# Initialize Cloudinary
cloudinary.config(
    cloud_name='dfzofzi0p',
    api_key='554485765384673',
    api_secret='SmCmz5vCySAZD3k8YQbvf9VF84Y'
)

# Define conversation states
IMAGE, CAPTION, SCHEDULE = range(3)

async def upload_image_to_cloudinary(image_path):
    """Upload image to Cloudinary asynchronously and return the URL"""
    url = "https://api.cloudinary.com/v1_1/dfzofzi0p/image/upload"
    
    with open(image_path, "rb") as file:
        form_data = aiohttp.FormData()
        form_data.add_field("file", file, filename=image_path, content_type="image/jpeg")
        form_data.add_field("upload_preset", "telegram_post_preset")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["secure_url"]
                else:
                    error_response = await response.text()
                    raise Exception(f"Failed to upload image to Cloudinary: {response.status} - {error_response}")

async def start(update: Update, context: CallbackContext):
    """Send a welcome message when the bot starts"""
    await update.message.reply_text("Welcome! Send me a photo and I'll upload it to Cloudinary.")

async def handle_photo(update: Update, context: CallbackContext):
    """Handles photo uploads from users."""
    if update.message.photo:
        photo = update.message.photo[-1]  # Get the highest resolution photo
        try:
            file = await photo.get_file()  # Get the file object asynchronously

            temp_dir = "temp"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            local_image_path = f"{temp_dir}/{file.file_id}.jpg"
            await file.download_to_drive(local_image_path)  # Save locally
            context.user_data["image_path"] = local_image_path

            context.user_data["image_url"] = await upload_image_to_cloudinary(local_image_path)

            await update.message.reply_text(
                f"Image uploaded successfully! URL: {context.user_data['image_url']}\n\n"
                "Please send the text you'd like to post with this image."
            )
            return CAPTION
        except Exception as e:
            await update.message.reply_text(f"Error handling the image: {e}")
            return ConversationHandler.END
    else:
        await update.message.reply_text("Please upload a valid photo.")
        return ConversationHandler.END

async def handle_caption(update: Update, context: CallbackContext):
    """Handles the caption/text for the uploaded image.""" 
    if "image_url" not in context.user_data:
        await update.message.reply_text("Please upload an image first.")
        return ConversationHandler.END

    caption = update.message.text
    context.user_data["caption"] = caption
    await update.message.reply_text(
        "When would you like to publish this post? Please send the time in the format HH:MM (24-hour format)."
    )
    return SCHEDULE

async def handle_schedule_time(update: Update, context: CallbackContext):
    """Handles the scheduling time provided by the user."""
    if "image_url" not in context.user_data or "caption" not in context.user_data:
        await update.message.reply_text("Please upload an image and provide text before scheduling.")
        return ConversationHandler.END

    time_input = update.message.text
    try:
        scheduled_time = datetime.datetime.strptime(time_input, "%H:%M").time()
        now = datetime.datetime.now()

        # Combine the scheduled time with today's date
        scheduled_datetime = datetime.datetime.combine(now.date(), scheduled_time)

        # If the scheduled time is earlier today, set it for tomorrow
        if scheduled_datetime <= now:
            scheduled_datetime += datetime.timedelta(days=1)

        context.user_data["scheduled_datetime"] = scheduled_datetime

        context.application.job_queue.run_once(
            send_scheduled_post,
            when=scheduled_datetime - now,
            data={
                "chat_id": "-1002418901762",  # Replace with actual channel ID
                "photo": context.user_data["image_url"],
                "caption": context.user_data["caption"],
            },
        )
        await update.message.reply_text("Your post has been scheduled successfully!")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid time format. Please send the time in HH:MM format.")
        return SCHEDULE


async def send_scheduled_post(context: CallbackContext):
    """Send the scheduled post to the user-defined chat"""
    user_data = context.job.data
    image_url = user_data.get("photo")
    caption = user_data.get("caption")
    chat_id = user_data.get("chat_id")

    if chat_id:
        await context.bot.send_photo(chat_id=chat_id, photo=image_url, caption=caption)
    else:
        raise Exception("Chat ID is missing! Unable to send the post.")

async def cancel(update: Update, context: CallbackContext):
    """Cancels the conversation."""
    await update.message.reply_text("Operation canceled.")
    return ConversationHandler.END

def main():
    """Set up the bot"""
    application = Application.builder().token("7821220132:AAEFOJPOwVjFEVg-nDfKlMBCAD_03HkSZqA").build()

    # Fix: Ensure `JobQueue` is initialized by adding job_queue to the application
    job_queue = application.job_queue

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
        states={
            CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_caption)],
            SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_schedule_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
