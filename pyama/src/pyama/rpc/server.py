"""Stdio JSON-RPC server for pyama."""

from dataclasses import replace
import json
import logging
import sys
from threading import Lock, Thread

from pyama.rpc.artifacts import ArtifactStore
from pyama.rpc.codec import from_wire, to_wire
from pyama.tasks.backends import LocalTaskBackend
from pyama.tasks.manager import TaskManager
from pyama.types import (
    MergeTaskRequest,
    ModelFitTaskRequest,
    ModelFitTaskResultHandle,
    ProcessingTaskRequest,
    StatisticsTaskRequest,
    StatisticsTaskResultHandle,
    TaskKind,
    TaskRecord,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class PyamaRpcServer:
    """Serve pyama operations over stdio."""

    def __init__(self) -> None:
        self._manager = TaskManager()
        self._backend = LocalTaskBackend(self._manager)
        self._artifacts = ArtifactStore()
        self._write_lock = Lock()
        self._running = True
        self._wire_results: dict[str, object] = {}

    def serve_forever(self) -> None:
        while self._running:
            line = sys.stdin.readline()
            if line == "":
                break
            line = line.strip()
            if not line:
                continue
            message = None
            try:
                message = json.loads(line)
                request_id = str(message.get("id"))
                method = str(message.get("method"))
                params = from_wire(message.get("params", {}))
                result = self._dispatch(
                    method, params if isinstance(params, dict) else {}
                )
                self._send_response(request_id, result=result)
            except Exception as exc:
                request_id = None
                if isinstance(message, dict) and message.get("id") is not None:
                    request_id = str(message.get("id"))
                self._send_response(
                    request_id,
                    error={"code": "internal_error", "message": str(exc)},
                )
        self._artifacts.cleanup()

    def _dispatch(self, method: str, params: dict[str, object]) -> object:
        if method == "system.ping":
            return {"ok": True}
        if method == "system.shutdown":
            self._running = False
            return {"ok": True}
        if method == "tasks.submit_processing":
            request = params["request"]
            if not isinstance(request, ProcessingTaskRequest):
                raise TypeError("Invalid processing request")
            record = self._backend.submit_processing(request)
            self._start_task_forwarder(record.id)
            return self._wire_task_record(record)
        if method == "tasks.submit_merge":
            request = params["request"]
            if not isinstance(request, MergeTaskRequest):
                raise TypeError("Invalid merge request")
            record = self._backend.submit_merge(request)
            self._start_task_forwarder(record.id)
            return self._wire_task_record(record)
        if method == "tasks.submit_model_fit":
            request = params["request"]
            if not isinstance(request, ModelFitTaskRequest):
                raise TypeError("Invalid model fit request")
            record = self._backend.submit_model_fit(request)
            self._start_task_forwarder(record.id)
            return self._wire_task_record(record)
        if method == "tasks.submit_statistics":
            request = params["request"]
            if not isinstance(request, StatisticsTaskRequest):
                raise TypeError("Invalid statistics request")
            record = self._backend.submit_statistics(request)
            self._start_task_forwarder(record.id)
            return self._wire_task_record(record)
        if method == "tasks.get_task":
            task_id = str(params["task_id"])
            record = self._backend.get_task(task_id)
            return None if record is None else self._wire_task_record(record)
        if method == "tasks.list_tasks":
            return [
                self._wire_task_record(record) for record in self._backend.list_tasks()
            ]
        if method == "tasks.cancel_task":
            return self._backend.cancel_task(str(params["task_id"]))
        raise ValueError(f"Unknown RPC method: {method}")

    def _wire_task_record(self, record: TaskRecord) -> TaskRecord:
        return replace(record, result=self._wire_task_result(record))

    def _wire_task_result(self, record: TaskRecord) -> object:
        if record.id in self._wire_results:
            return self._wire_results[record.id]
        result = record.result
        if result is None or record.status != TaskStatus.COMPLETED:
            return result
        if record.kind == TaskKind.MODEL_FIT:
            results_df, saved_csv_path = result
            wire_result = ModelFitTaskResultHandle(
                results_table=(
                    None
                    if results_df is None
                    else self._artifacts.write_dataframe(
                        results_df, kind="model_fit_results"
                    )
                ),
                saved_csv_path=saved_csv_path,
            )
            self._wire_results[record.id] = wire_result
            return wire_result
        if record.kind == TaskKind.STATISTICS:
            results_df, traces_by_sample, output_path = result
            wire_result = StatisticsTaskResultHandle(
                results_table=self._artifacts.write_dataframe(
                    results_df,
                    kind="statistics_results",
                ),
                trace_tables={
                    sample_name: self._artifacts.write_dataframe(
                        sample_df,
                        kind=f"statistics_trace_{sample_name}",
                    )
                    for sample_name, sample_df in traces_by_sample.items()
                },
                output_path=output_path,
            )
            self._wire_results[record.id] = wire_result
            return wire_result
        return result

    def _start_task_forwarder(self, task_id: str) -> None:
        queue = self._backend.subscribe(task_id)

        def _forward() -> None:
            try:
                while True:
                    snapshot = queue.get()
                    self._send_notification(
                        "events.task_snapshot",
                        {"snapshot": self._wire_task_record(snapshot)},
                    )
                    if snapshot.status in {
                        snapshot.status.__class__.COMPLETED,
                        snapshot.status.__class__.FAILED,
                        snapshot.status.__class__.CANCELLED,
                    }:
                        return
            finally:
                self._backend.unsubscribe(task_id, queue)

        Thread(target=_forward, daemon=True).start()

    def _send_response(
        self,
        request_id: str | None,
        *,
        result: object | None = None,
        error: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = to_wire(result)
        self._write_message(payload)

    def _send_notification(self, method: str, params: dict[str, object]) -> None:
        self._write_message(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": to_wire(params),
            }
        )

    def _write_message(self, payload: dict[str, object]) -> None:
        with self._write_lock:
            sys.stdout.write(f"{json.dumps(payload)}\n")
            sys.stdout.flush()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    server = PyamaRpcServer()
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover - module entrypoint
    main()
