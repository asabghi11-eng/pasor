import asyncio
import json
import websockets

URL = "ws://127.0.0.1:8000/ws"


def act_message(state):
    s = state
    if s["phase"] == "choosing-trump" and s["turn"] == s["mySeat"]:
        hand = s["hand"]
        counts = {}
        for c in hand:
            counts[c["suit"]] = counts.get(c["suit"], 0) + 1
        suit = max(counts, key=counts.get)
        return {"type": "choose_trump", "suit": suit}
    if s["phase"] == "playing" and s["turn"] == s["mySeat"]:
        hand = s["hand"]
        led = s["currentTrick"][0]["card"]["suit"] if s["currentTrick"] else None
        legal = [c for c in hand if c["suit"] == led] if led else []
        if not legal:
            legal = hand
        return {"type": "play_card", "card": legal[0]}
    return None


async def main():
    ws1 = await websockets.connect(URL)
    ws2 = await websockets.connect(URL)
    await ws1.send(json.dumps({"type": "login", "name": "A"}))
    await ws2.send(json.dumps({"type": "login", "name": "B"}))

    token1 = None
    plays_by_A = 0
    disconnected = False
    saw_partner_disconnected = False

    async def pump(ws, tag):
        nonlocal token1, plays_by_A, disconnected, saw_partner_disconnected
        async for raw in ws:
            msg = json.loads(raw)
            print(f"[{tag}] <- {msg.get('type')} phase={msg.get('phase')} turn={msg.get('turn')}", flush=True)
            if msg["type"] == "login_ok" and tag == "A":
                token1 = msg["session_token"]
            if msg["type"] in ("login_ok",):
                await ws.send(json.dumps({"type": "quick_match"}))
            if msg["type"] == "game_state":
                if tag == "B" and not msg["partnerConnected"]:
                    saw_partner_disconnected = True
                m = act_message(msg)
                if m:
                    await asyncio.sleep(0.05)
                    await ws.send(json.dumps(m))
                    if tag == "A":
                        plays_by_A += 1
                        if plays_by_A >= 2 and not disconnected:
                            disconnected = True
                            await asyncio.sleep(0.3)
                            print(">>> A disconnecting now <<<", flush=True)
                            await ws.close()
                            return

    t1 = asyncio.create_task(pump(ws1, "A"))
    t2 = asyncio.create_task(pump(ws2, "B"))

    try:
        await asyncio.wait_for(t1, timeout=15)
    except asyncio.TimeoutError:
        pass

    await asyncio.sleep(8)  # long enough to cross the (shortened) grace period at least once
    print("saw_partner_disconnected on B:", saw_partner_disconnected)

    print(">>> reconnecting A <<<", flush=True)
    ws1b = await websockets.connect(URL)
    await ws1b.send(json.dumps({"type": "reconnect", "session_token": token1}))

    async def pump_after_reconnect(ws, tag):
        async for raw in ws:
            msg = json.loads(raw)
            print(f"[{tag}] <- {msg.get('type')} phase={msg.get('phase')} turn={msg.get('turn')} partnerConnected={msg.get('partnerConnected')}", flush=True)
            m = act_message(msg) if msg.get("type") == "game_state" else None
            if m:
                await asyncio.sleep(0.05)
                await ws.send(json.dumps(m))

    t1b = asyncio.create_task(pump_after_reconnect(ws1b, "A-reconnected"))
    await asyncio.sleep(6)
    t1b.cancel()
    t2.cancel()
    await ws1b.close()
    await ws2.close()
    print("RECONNECT TEST DONE")


asyncio.run(main())