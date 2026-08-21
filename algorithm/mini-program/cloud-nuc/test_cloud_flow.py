"""Offline state-machine test; uses tiny FastAPI stubs when FastAPI is absent."""

import base64
import importlib
import os
import sys
import tempfile
import types
import unittest


def install_fastapi_stubs():
    try:
        import fastapi  # noqa: F401
        return
    except ImportError:
        pass

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def _route(self, *args, **kwargs):
            return lambda function: function

        get = post = _route

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = FastAPI
    fastapi.HTTPException = HTTPException
    fastapi.Depends = lambda value=None: value
    fastapi.Header = lambda default=None: default
    fastapi.Query = lambda default=None, *args, **kwargs: default
    middleware = types.ModuleType("fastapi.middleware")
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object
    responses = types.ModuleType("fastapi.responses")
    responses.FileResponse = lambda path: path
    sys.modules.update({
        "fastapi": fastapi,
        "fastapi.middleware": middleware,
        "fastapi.middleware.cors": cors,
        "fastapi.responses": responses,
    })


class CloudFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fastapi_stubs()
        cls.tempdir = tempfile.TemporaryDirectory()
        os.environ["BIOSHUTTLE_DB"] = os.path.join(cls.tempdir.name, "test.db")
        os.environ["BIOSHUTTLE_EVIDENCE_DIR"] = os.path.join(cls.tempdir.name, "evidence")
        cls.api = importlib.import_module("cloud_main")

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_full_delivery(self):
        api = self.api
        created = api.create_task_record(api.TaskCreate(
            sample_name="血清",
            temp_humidity="2-8C",
            sender_id="A",
            origin=api.Location(name="A点", latitude=22.89, longitude=113.47),
            target=api.Location(name="B点", latitude=22.90, longitude=113.48),
        ))
        sample_code = created["sample_code"]
        pickup_code = created["pickup_code"]
        self.assertTrue(sample_code.startswith("BS"))
        self.assertEqual(len(pickup_code), 4)

        first = api.next_command("test-nuc")["command"]
        self.assertEqual(first["type"], "run_delivery")
        for event in ("departed_for_origin", "origin_opened", "origin_loaded", "destination_arrived"):
            api.robot_event(api.RobotEvent(sample_code=sample_code, event=event))
        self.assertEqual(api.task_status(sample_code)["status"], "awaiting_pickup")

        with self.assertRaises(api.HTTPException) as wrong:
            api.pickup(api.PickupRequest(sample_code=sample_code, pickup_code="99999"))
        self.assertEqual(wrong.exception.status_code, 400)

        pickup_result = api.pickup(api.PickupRequest(sample_code=sample_code, pickup_code=pickup_code))
        self.assertEqual(pickup_result["status"], "pickup_requested")
        second = api.next_command("test-nuc")["command"]
        self.assertEqual(second["type"], "release_sample")
        api.robot_event(api.RobotEvent(sample_code=sample_code, event="destination_opened"))
        api.robot_event(api.RobotEvent(sample_code=sample_code, event="completed"))
        evidence = api.EvidenceUpload(
            filename="destination_after_close.txt",
            phase="destination_after_close",
            content_base64=base64.b64encode(b"test evidence").decode("ascii"),
        )
        ack = api.ack_command(second["id"], api.CommandAck(success=True, message="ok", evidence=[evidence]))
        self.assertEqual(ack["state"], "done")
        final = api.task_status(sample_code)
        self.assertEqual(final["status"], "completed")
        self.assertEqual(len(final["evidence"]), 1)


if __name__ == "__main__":
    unittest.main()
