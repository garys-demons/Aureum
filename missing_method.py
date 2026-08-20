    async def _run_order_book_stream(self, symbol: str, queue: asyncio.Queue) -> None:
        """
        Maintain a reconciled local order book for `symbol` (TRD §6.1).

        On initial connect and on ANY disconnect, this does NOT simply
        resubscribe — it re-runs the full reconciliation procedure:
        buffer live deltas, fetch a fresh REST snapshot, find the correct
        starting delta, and verify contiguity. Any gap triggers a full
        re-reconciliation, not a skip (TRD §6.1 step 6, §6.2).
        """
        from services.market_data.order_book import fetch_snapshot, reconcile
        from services.market_data.parsers import parse_order_book_delta

        stream_url = f"wss://stream.testnet.binance.vision/ws/{symbol.lower()}@depth"
        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            try:
                logger.info("order_book_connecting", symbol=symbol)
                async with websockets.connect(stream_url) as ws:
                    self._active_connections[f"order_book_{symbol}"] = ws
                    logger.info("order_book_reconciling", symbol=symbol)
                    backoff = INITIAL_BACKOFF_SECONDS
                    # Buffer live deltas while the REST snapshot is fetched
                    # (TRD §6.1 steps 2-3), PLUS a minimum extra window after
                    # the fetch completes — depth updates don't arrive on a
                    # fixed schedule, so buffering only as long as the fetch
                    # itself takes is often too short to catch a bridging
                    # delta (observed repeatedly in Phase 1/2 testing).
                    MIN_BUFFER_SECONDS_AFTER_SNAPSHOT = 2.0

                    buffered_deltas = []
                    snapshot_task = asyncio.create_task(fetch_snapshot(symbol))
                    snapshot = None
                    buffer_deadline = None

                    while True:
                        if snapshot_task.done() and snapshot is None:
                            snapshot = snapshot_task.result()
                            buffer_deadline = (
                                asyncio.get_event_loop().time() + MIN_BUFFER_SECONDS_AFTER_SNAPSHOT
                            )

                        if buffer_deadline is not None and asyncio.get_event_loop().time() >= buffer_deadline:
                            break

                        try:
                            raw_message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue

                        raw = json.loads(raw_message)
                        wrapped = {"stream": f"{symbol.lower()}@depth", "data": raw}
                        buffered_deltas.append(parse_order_book_delta(wrapped))

                    # Find the correct starting point and verify contiguity
                    # (TRD §6.1 steps 4-6). Any failure -> re-fetch and retry.
                    try:
                        ordered_deltas = reconcile(snapshot, buffered_deltas)
                    except ValueError as e:
                        logger.warning(
                            "order_book_reconciliation_failed_retrying",
                            symbol=symbol,
                            error=str(e),
                        )
                        continue  # re-enter outer loop: fresh connect + fresh snapshot

                    await queue.put(snapshot)
                    last_update_id = snapshot.last_update_id
                    for delta in ordered_deltas:
                        await queue.put(delta)
                        last_update_id = delta.final_update_id

                    logger.info("order_book_live", symbol=symbol, last_update_id=last_update_id)

                    # Now "live" — forward each new delta, verifying it
                    # connects exactly to the previous one.
                    async for raw_message in ws:
                        raw = json.loads(raw_message)
                        wrapped = {"stream": f"{symbol.lower()}@depth", "data": raw}
                        delta = parse_order_book_delta(wrapped)

                        if delta.first_update_id != last_update_id + 1:
                            logger.warning(
                                "order_book_gap_detected_reconciling",
                                symbol=symbol,
                                expected=last_update_id + 1,
                                got=delta.first_update_id,
                            )
                            break  # exit inner loop -> full reconciliation restarts

                        await queue.put(delta)
                        last_update_id = delta.final_update_id

            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning(
                    "order_book_disconnected_retrying",
                    symbol=symbol,
                    error=str(e),
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

