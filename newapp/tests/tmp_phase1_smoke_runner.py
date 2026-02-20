import json

results = []
logs = []


def record(item, ok, detail=""):
    results.append({"item": item, "ok": bool(ok), "detail": detail})


try:
    from fastapi.testclient import TestClient
    from newapp.src.api.main import app
except Exception as e:
    print(json.dumps({"fatal_import_error": str(e)}))
    raise


try:
    with TestClient(app) as client:
        has_container = hasattr(app.state, "container")
        record(
            "startup_container_created",
            has_container,
            "app.state.container exists" if has_container else "missing container",
        )

        for path in ["/", "/home", "/charts", "/charts-clean", "/monitor", "/backtest"]:
            try:
                response = client.get(path, follow_redirects=False)
                if path == "/":
                    ok = response.status_code in (301, 302, 307, 308)
                else:
                    ok = response.status_code == 200
                record(f"GET {path}", ok, f"status={response.status_code}")
            except Exception as exc:
                record(f"GET {path}", False, f"exception={exc}")

        for path in ["/api/ohlc", "/api/analysis", "/api/combined"]:
            try:
                response = client.get(path)
                ok = response.status_code == 200
                detail = f"status={response.status_code}"
                if not ok:
                    try:
                        detail += f" body={response.json()}"
                    except Exception:
                        detail += f" body={response.text[:300]}"
                record(f"GET {path}", ok, detail)
            except Exception as exc:
                record(f"GET {path}", False, f"exception={exc}")

        try:
            response = client.get("/api/ohlc", params={"limit": 999999})
            record(
                "GET /api/ohlc invalid limit",
                400 <= response.status_code < 500,
                f"status={response.status_code}",
            )
        except Exception as exc:
            record("GET /api/ohlc invalid limit", False, f"exception={exc}")

        try:
            response = client.post(
                "/api/monitor/start",
                json={"ticker": "WDO$", "timeframe": "M5"},
            )
            payload = response.json()
            ok = response.status_code == 200 and payload.get("status") in (
                "started",
                "already_running",
            )
            record(
                "POST /api/monitor/start",
                ok,
                f"status={response.status_code} body={payload}",
            )
        except Exception as exc:
            record("POST /api/monitor/start", False, f"exception={exc}")

        try:
            response = client.get("/api/monitor/status")
            payload = response.json()
            ok = response.status_code == 200 and "active_monitors" in payload
            record(
                "GET /api/monitor/status",
                ok,
                f"status={response.status_code} body={payload}",
            )
        except Exception as exc:
            record("GET /api/monitor/status", False, f"exception={exc}")

        try:
            response = client.post(
                "/api/monitor/stop",
                json={"ticker": "WDO$", "timeframe": "M5"},
            )
            payload = response.json()
            ok = response.status_code == 200 and payload.get("status") in (
                "stopped",
                "not_found",
            )
            record(
                "POST /api/monitor/stop",
                ok,
                f"status={response.status_code} body={payload}",
            )
        except Exception as exc:
            record("POST /api/monitor/stop", False, f"exception={exc}")

        try:
            response = client.post(
                "/api/monitor/stop",
                json={"ticker": "WDO$", "timeframe": "M5"},
            )
            payload = response.json()
            ok = response.status_code == 200 and payload.get("status") == "not_found"
            record(
                "POST /api/monitor/stop repeated",
                ok,
                f"status={response.status_code} body={payload}",
            )
        except Exception as exc:
            record("POST /api/monitor/stop repeated", False, f"exception={exc}")

        try:
            response = client.get(
                "/api/monitor-predictions",
                params={"symbol": "WDO$", "timeframe": "M5", "count": 10},
            )
            payload = response.json()
            ok_top = response.status_code == 200 and all(
                key in payload for key in ["predictions", "latest_candle_time", "is_market_open"]
            )
            ok_item = True
            detail = f"status={response.status_code}"
            if payload.get("predictions"):
                first = payload["predictions"][0]
                required = [
                    "timestamp",
                    "tipo",
                    "direction",
                    "preco",
                    "prob_ml",
                    "mensagem",
                    "indicators",
                    "analysis",
                ]
                ok_item = all(key in first for key in required)
                if ok_item:
                    ok_item = all(
                        key in first["analysis"]
                        for key in [
                            "trend",
                            "trend_strength",
                            "rsi",
                            "rsi_condition",
                            "support",
                            "resistance",
                            "pattern",
                            "signal_valid",
                        ]
                    )
                detail += f" predictions={len(payload.get('predictions', []))}"
            else:
                detail += f" predictions=0 error={payload.get('error')}"
            record("GET /api/monitor-predictions contract", ok_top and ok_item, detail)
        except Exception as exc:
            record("GET /api/monitor-predictions contract", False, f"exception={exc}")

        try:
            with client.websocket_connect("/ws/monitor") as websocket:
                websocket.send_text("ping")
                msg = websocket.receive_json()
                ok = msg.get("type") == "pong"
                record("WS /ws/monitor connect+pong", ok, f"msg={msg}")
        except Exception as exc:
            record("WS /ws/monitor connect+pong", False, f"exception={exc}")

        try:
            with client.websocket_connect("/ws/backtest") as websocket:
                websocket.send_json(
                    {
                        "action": "start",
                        "symbol": "WDO$",
                        "timeframe": "M5",
                        "start": "2025-01-01T00:00:00",
                        "end": "2025-01-02T00:00:00",
                        "initial_capital": 100000,
                        "position_size": 1,
                        "update_interval": 5,
                    }
                )
                msg = websocket.receive_json()
                ok = msg.get("type") in ("init", "error")
                record(
                    "WS /ws/backtest connect+first_message",
                    ok,
                    f"msg_type={msg.get('type')} msg={msg}",
                )
        except Exception as exc:
            record("WS /ws/backtest connect+first_message", False, f"exception={exc}")

    record("shutdown_executed_best_effort", True, "TestClient context exited")
except Exception as exc:
    logs.append(f"testclient run exception: {exc}")

print(json.dumps({"results": results, "logs": logs}, ensure_ascii=False))
