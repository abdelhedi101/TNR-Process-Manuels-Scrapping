
"""MQ helper script that preserves stdlib queue compatibility.

This file is intentionally named queue.py in the workspace. To avoid breaking
third-party imports (for example Playwright internals importing stdlib queue),
we mirror Python's stdlib queue symbols at import time and keep MQ logic under
an explicit main entry point only.
"""

from importlib import util as importlib_util
from pathlib import Path
import sysconfig


def _load_stdlib_queue_symbols() -> None:
    stdlib_queue_path = Path(sysconfig.get_path("stdlib")) / "queue.py"
    spec = importlib_util.spec_from_file_location("_stdlib_queue", stdlib_queue_path)
    if spec is None or spec.loader is None:
        return
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name in dir(module):
        if name.startswith("__") and name not in {"__all__", "__doc__"}:
            continue
        globals()[name] = getattr(module, name)


def run_mq_sample() -> None:
    import pymqi

    queue_manager = "QM1"
    channel = "DEV.APP.SVRCONN"
    conn_info = "localhost(1414)"
    queue_name = "DEV.QUEUE.1"
    user = "app"
    password = "passw0rd"

    cd = pymqi.CD()
    cd.ChannelName = channel
    cd.ConnectionName = conn_info
    cd.ChannelType = pymqi.CMQC.MQCHT_CLNTCONN
    cd.TransportType = pymqi.CMQC.MQXPT_TCP

    sco = pymqi.SCO()
    qmgr = pymqi.QueueManager(None)

    qmgr.connect_with_options(
        queue_manager,
        user=user,
        password=password,
        cd=cd,
        sco=sco,
    )

    mq_queue = pymqi.Queue(qmgr, queue_name)
    try:
        message = mq_queue.get()
        print("Message recu :", message.decode("utf-8"))
    except pymqi.MQMIError as exc:
        if exc.reason == pymqi.CMQC.MQRC_NO_MSG_AVAILABLE:
            print("Aucun message disponible dans la queue")
        else:
            print(f"Erreur MQ : {exc}")
    finally:
        mq_queue.close()
        qmgr.disconnect()


_load_stdlib_queue_symbols()


if __name__ == "__main__":
    run_mq_sample()