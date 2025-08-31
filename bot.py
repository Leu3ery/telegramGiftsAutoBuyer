# pip install telethon
import asyncio
import json
from pathlib import Path
import time
from telethon import TelegramClient, functions, types
from telethon.errors import RPCError
from dotenv import load_dotenv
import os

load_dotenv()

API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE    = os.getenv("PHONE")
SESSION  = os.getenv("SESSION", "stars_autobuyer_all")
CHECK_EVERY_SEC = int(os.getenv("CHECK_EVERY_SEC", 10))
CHANNEL_PREFIX = os.getenv("CHANNEL_PREFIX", "⭐ Gift")
INCLUDE_UPGRADE = os.getenv("INCLUDE_UPGRADE", "false").lower() == "true"
GIFTSCOUNT = int(os.getenv("GIFTSCOUNT", 10000))

# def load_known():
#     if STATE_FILE.exists():
#         try:
#             return set(json.loads(STATE_FILE.read_text("utf-8")))
#         except Exception:
#             pass
#     return set()

# def save_known(known: set[str]):
#     STATE_FILE.write_text(json.dumps(sorted(known)), "utf-8")

async def create_channel_for_gift(client, gift_id, price):
    title = f"⭐ Gift #{gift_id} — {price}⭐"
    about = f"Канал для подарка #{gift_id} ({price}⭐)."

    upd = await client(functions.channels.CreateChannelRequest(
        broadcast=True, megagroup=False, forum=False,
        title=title, about=about
    ))

    # из updates вытаскиваем канал
    if upd.chats:
        channel = upd.chats[0]
        return await client.get_input_entity(channel)

    # если почему-то пусто — ищем по диалогам
    async for d in client.iter_dialogs():
        if d.is_channel and getattr(d.entity, "title", "") == title:
            return await client.get_input_entity(d.entity)

    raise RuntimeError("Не удалось создать канал")

async def buy_gift(client, channel, gift_id):
    invoice = types.InputInvoiceStarGift(
        peer=channel,
        gift_id=gift_id,
        include_upgrade=INCLUDE_UPGRADE
    )
    form = await client(functions.payments.GetPaymentFormRequest(invoice=invoice))
    res = await client(functions.payments.SendStarsFormRequest(
        form_id=form.form_id,
        invoice=invoice
    ))
    return res

async def get_stars_balance(client: TelegramClient) -> int:
    me = types.InputPeerSelf()  # або: me = await client.get_input_entity('me')
    status = await client(functions.payments.GetStarsStatusRequest(peer=me))
    # У різних версіях схеми balance може бути числом або об'єктом з .amount
    return getattr(status.balance, "amount", status.balance)

async def monitor(client):
    # known = load_known()
    starsAmount = await get_stars_balance(client)
    print(starsAmount)
    while True:
        try:
            catalog = await client(functions.payments.GetStarGiftsRequest(hash=0))
            gifts = list(getattr(catalog, "gifts", []))

            # новые подарки
            new_gifts = [(int(g.id), int(getattr(g, "stars", getattr(g, "star_count", 0)) or 0), bool(g.limited), bool(g.sold_out))
                         for g in gifts if g.limited and not g.sold_out]
            
            print(new_gifts)

            if new_gifts:
                # сортируем по цене
                new_gifts.sort(key=lambda x: x[1])
                cheepest = new_gifts[0]
  
                # помечаем все новые как известные, чтобы не повторять
                # for gid, stars, isLimited, isSoldOut in new_gifts:
                #     known.add(str(gid))
                # save_known(known)

                # цикл: покупаем самый дешёвый до тех пор, пока не кончатся Stars

                gid, price, isLimited, isSoldOut = cheepest
                for _ in range(min(GIFTSCOUNT, starsAmount//price)):
                    print(f"Пробую купить подарок {gid} за {price}⭐")
                    try:
                        channel = await create_channel_for_gift(client, gid, price)
                        res = await buy_gift(client, channel, gid)
                        print("✅ Успех:", type(res).__name__)
                        # print("success")
                    except RPCError as e:
                        if "BALANCE_TOO_LOW" in str(e):
                            print("❌ Недостаточно Stars. Останавливаюсь.")
                            break
                        else:
                            print("❌ Ошибка:", e)
                    time.sleep(1)
        except Exception as e:
            print("⚠️ Ошибка цикла:", e)

        await asyncio.sleep(CHECK_EVERY_SEC)

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start(phone=PHONE)
    print("Авторизован, мониторинг запущен…")
    await monitor(client)

if __name__ == "__main__":
    asyncio.run(main())