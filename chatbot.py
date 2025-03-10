from telegram import Update
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, CallbackContext)
import configparser
import logging
import redis
from ChatGPT_HKBU import HKBU_ChatGPT

global redis1

# 保存用户兴趣与段位信息到 Redis
def save_user_interest_and_rank(user_id, interest, rank):
    """保存用户的兴趣和段位到 Redis 数据库"""
    redis1.sadd(f"user:{user_id}:interests", interest)  # 使用集合存储兴趣
    redis1.set(f"user:{user_id}:rank", rank)           # 使用字符串存储段位
    logging.info(f"Saved interest '{interest}' and rank '{rank}' for user {user_id}")

# 匹配兴趣相似且段位接近的用户
def match_users_by_interest_and_rank(user_id):
    """根据兴趣和段位进行用户匹配"""
    user_interests = redis1.smembers(f"user:{user_id}:interests")
    user_rank = redis1.get(f"user:{user_id}:rank")
    matched_users = []

    if not user_rank or not user_interests:
        return []  # 如果用户数据不完整，返回空列表

    for key in redis1.keys("user:*:interests"):
        other_user_id = key.decode().split(":")[1]
        if other_user_id == user_id:
            continue  # 跳过匹配自己

        # 获取其他用户数据
        other_user_interests = redis1.smembers(key)
        other_user_rank = redis1.get(f"user:{other_user_id}:rank")

        # 判断兴趣是否有交集和段位是否接近
        if user_interests.intersection(other_user_interests) and abs(int(user_rank) - int(other_user_rank)) <= 1:
            matched_users.append(other_user_id)
    
    return matched_users

# 设置用户兴趣和段位
def set_interest_and_rank(update: Update, context: CallbackContext):
    """处理 /set_interest_and_rank 命令，保存兴趣和段位"""
    user_id = str(update.effective_chat.id)
    try:
        interest = context.args[0]  # 用户输入兴趣
        rank = context.args[1]      # 用户输入段位
        save_user_interest_and_rank(user_id, interest, rank)
        update.message.reply_text(f"你的兴趣 '{interest}' 和段位 '{rank}' 已保存！")
    except (IndexError, ValueError):
        update.message.reply_text("用法：/set_interest_and_rank <兴趣> <段位>")

# 匹配用户命令
def match_users(update: Update, context: CallbackContext):
    """处理 /match_users 命令，返回匹配用户列表"""
    user_id = str(update.effective_chat.id)
    matches = match_users_by_interest_and_rank(user_id)
    if matches:
        update.message.reply_text(f"匹配到的用户：{', '.join(matches)}")
    else:
        update.message.reply_text("暂时没有匹配到任何用户。")

# 调用 ChatGPT
def equiped_chatgpt(update, context):
    global chatgpt
    reply_message = chatgpt.submit(update.message.text)
    logging.info("Update: " + str(update))
    logging.info("context: " + str(context))
    context.bot.send_message(chat_id=update.effective_chat.id, text=reply_message)

# 帮助命令
def help_command(update: Update, context: CallbackContext):
    """提供帮助信息"""
    update.message.reply_text("使用以下命令：\n"
                              "/set_interest_and_rank <兴趣> <段位> - 设置你的兴趣和游戏段位\n"
                              "/match_users - 匹配相似兴趣和段位的用户\n"
                              "/help - 获取帮助信息")

# 初始化主函数
def main():
    # 加载配置文件
    config = configparser.ConfigParser()
    config.read('config.ini')

    # 初始化 Telegram Bot
    updater = Updater(token=(config['TELEGRAM']['ACCESS_TOKEN']), use_context=True)
    dispatcher = updater.dispatcher

    # 初始化 Redis
    global redis1
    redis1 = redis.Redis(
        host=config['REDIS']['HOST'],
        port=config['REDIS']['PORT'],
        decode_responses=True,
        username=config['REDIS']['USERNAME'],
        password=config['REDIS']['PASSWORD']
    )

    # 设置日志模块
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    # 注册命令处理程序
    dispatcher.add_handler(CommandHandler("set_interest_and_rank", set_interest_and_rank))
    dispatcher.add_handler(CommandHandler("match_users", match_users))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # 注册消息处理器
    chatgpt_handler = MessageHandler(Filters.text & (~Filters.command), equiped_chatgpt)
    dispatcher.add_handler(chatgpt_handler)

    # 启动机器人
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
