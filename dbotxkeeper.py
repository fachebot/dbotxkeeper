import os
import json
import time
import signal
import aiohttp
import asyncio
import logging
from web3 import Web3

filename = "data/db.json"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DbotxClient():
    def __init__(self, apikey: str, chain: str, wallet_id: str):
        self.chain = chain
        self.apikey = apikey
        self.wallet_id = wallet_id

    async def sell_all(self, token: str):
        url = "https://api-bot-v1.dbotx.com/automation/swap_order"
        payload = {
            "chain": self.chain,
            "pair": token,
            "walletId": self.wallet_id,
            "type": "sell",
            "gasFeeDelta": 15,
            "maxFeePerGas": 100,
            "maxSlippage": 0.1,
            "concurrentNodes": 2,
            "retries": 5,
            "amountOrPercent": 1.0
        }
        headers = {"x-api-key": self.apikey}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                return data["res"]

    async def get_follow_trades(self, my_wallet: str, target_wallet: str):
        url = "https://api-bot-v1.dbotx.com/account/follow_trades"
        params = {
            "chain": self.chain,
            "type": "buy",
            "myWallet": Web3.to_checksum_address(my_wallet),
            "targetWallet": Web3.to_checksum_address(target_wallet),
            "page": 0,
            "size": 20,
        }
        headers = {"x-api-key": self.apikey, "cache-control": "no-cache"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
                return [v for v in data["res"] if v["state"] != "fail"]


def init_db():
    directory = os.path.dirname(filename)
    if not os.path.exists(directory):
        os.makedirs(directory)

    if not os.path.isfile(filename):
        with open(filename, "w") as file:
            unix_timestamp = int(time.time() * 1000)
            file.write(json.dumps({"last_order_create_time": unix_timestamp}))

    with open(filename, "r") as fp:
        return json.load(fp)


def flush_db(db: dict):
    with open(filename, "w") as fp:
        fp.write(json.dumps(db))


class Worker():
    def __init__(self, db: dict, client: DbotxClient, my_wallet: str, target_wallet: str, sell_delay_seconds: int):
        self.db = db
        self.trades = []
        self.client = client
        self.my_wallet = my_wallet
        self.target_wallet = target_wallet
        self.sell_delay_seconds = sell_delay_seconds
        self.cursor = self.db["last_order_create_time"]

        self.should_exit = False

    def set_exit(self):
        self.should_exit = True

    async def check_follow_trades(self):
        while not self.should_exit:
            try:
                trades = await self.client.get_follow_trades(self.my_wallet, self.target_wallet)
                trades.reverse()
                
                for trade in trades:
                    create_at = trade["createAt"]
                    if create_at <= self.cursor:
                        continue

                    self.cursor = create_at
                    self.trades.append(trade)
                    logging.info(f"检查到新的跟单交易: {trade}")

                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(f"获取跟单交易失败, {str(e)}")
                await asyncio.sleep(0.5)

    async def check_timeout_follow_trades(self):
        while not self.should_exit:
            if len(self.trades) == 0:
                await asyncio.sleep(0.1)
                continue

            trade = self.trades[0]
            create_at = trade["createAt"]
            unix_timestamp = int(time.time() * 1000)
            if create_at + self.sell_delay_seconds * 1000 >= unix_timestamp:
                await asyncio.sleep(0.1)
                continue

            try:
                token = trade["receive"]["info"]["contract"]
                res = await self.client.sell_all(token)

                self.db["last_order_create_time"] = create_at
                flush_db(self.db)

                self.trades = self.trades[1:]
                logging.info(f"卖出代币完成, token: {token}, id: {res['id']}")
            except Exception as e:
                logging.error(f"卖出代币失败, token: {token}, {str(e)}")


def signal_handler(worker):
    worker.set_exit()


async def main():
    db = init_db()
    flush_db(db)

    with open("config.json", "r") as fp:
        config = json.load(fp)

    client = DbotxClient(
        config["apikey"], config["chain"], config["wallet_id"])
    worker = Worker(db, client, config["my_wallet"],
                    config["target_wallet"], config["sell_delay_seconds"])

    signal.signal(signal.SIGINT, lambda s, f: signal_handler(worker))
    logging.info("脚本已启动, 正在持续监控跟单交易...")

    await asyncio.gather(
        worker.check_follow_trades(),
        worker.check_timeout_follow_trades()
    )

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
