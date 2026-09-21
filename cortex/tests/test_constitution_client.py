import json
import struct
from unittest.mock import MagicMock, patch

import pytest
from cortex.constitution_client import ConstitutionIPCClient, ConstitutionStatus


class TestBuildEnvelope:
    def test_envelope_structure(self):
        client = ConstitutionIPCClient()
        raw = client._build_envelope("Heartbeat", "{}")
        env = json.loads(raw)
        assert env["protocol_version"] == 1
        assert env["opcode"] == "Heartbeat"
        assert env["payload"] == "{}"
        assert "request_id" in env

    def test_utf8_encoding(self):
        client = ConstitutionIPCClient()
        raw = client._build_envelope("EvaluateProposal", '{"key": "val"}')
        assert isinstance(raw, bytes)
        env = json.loads(raw)
        assert env["opcode"] == "EvaluateProposal"


class TestReadExact:
    def test_reads_exact_bytes(self):
        sock = MagicMock()
        sock.recv.side_effect = [b"abc", b"de"]
        result = ConstitutionIPCClient._read_exact(sock, 5)
        assert result == b"abcde"

    def test_raises_on_early_close(self):
        sock = MagicMock()
        sock.recv.return_value = b""
        with pytest.raises(ConnectionError, match="closed early"):
            ConstitutionIPCClient._read_exact(sock, 10)


class TestSendFrame:
    def test_no_session_raises(self):
        client = ConstitutionIPCClient()
        with pytest.raises(ConnectionError, match="No active session"):
            client._send_frame(b"test")

    def test_sends_length_prefixed_frame(self):
        client = ConstitutionIPCClient()
        mock_sock = MagicMock()
        # Simulate: 4-byte header + response body
        response_body = b'{"status": "ok"}'
        header = struct.pack(">I", len(response_body))
        mock_sock.recv.side_effect = [header, response_body]
        client._session_sock = mock_sock

        payload = b"test-payload"
        result = client._send_frame(payload)

        # Verify it sent length prefix + payload
        mock_sock.sendall.assert_called_once()
        sent = mock_sock.sendall.call_args[0][0]
        assert sent[:4] == struct.pack(">I", len(payload))
        assert sent[4:] == payload
        assert json.loads(result)["status"] == "ok"

    def test_zero_frame_length_raises(self):
        client = ConstitutionIPCClient()
        mock_sock = MagicMock()
        zero_header = struct.pack(">I", 0)
        mock_sock.recv.return_value = zero_header
        client._session_sock = mock_sock

        with pytest.raises(ValueError, match="Invalid response frame length"):
            client._send_frame(b"test")

    def test_oversized_frame_raises(self):
        client = ConstitutionIPCClient()
        mock_sock = MagicMock()
        big_header = struct.pack(">I", 999_999)
        mock_sock.recv.return_value = big_header
        client._session_sock = mock_sock

        with pytest.raises(ValueError, match="Invalid response frame length"):
            client._send_frame(b"test")


class TestSessionManagement:
    def test_context_manager(self):
        client = ConstitutionIPCClient()
        with patch.object(client, "open_session") as mock_open, patch.object(
            client, "close_session"
        ) as mock_close:
            with client:
                mock_open.assert_called_once()
            mock_close.assert_called_once()

    def test_close_idempotent(self):
        client = ConstitutionIPCClient()
        client._session_sock = MagicMock()
        client.close_session()
        assert client._session_sock is None
        # Second close should be fine
        client.close_session()


class TestRPCMethods:
    def _make_client_with_mock(self):
        client = ConstitutionIPCClient()
        mock_sock = MagicMock()
        client._session_sock = mock_sock
        return client, mock_sock

    def _mock_response(self, mock_sock, payload: dict):
        body = json.dumps(payload).encode()
        header = struct.pack(">I", len(body))
        mock_sock.recv.side_effect = [header, body]

    def test_heartbeat(self):
        client, sock = self._make_client_with_mock()
        self._mock_response(sock, {"alive": True, "protocol_version": 1})
        result = client.heartbeat()
        assert result["alive"] is True

    def test_status(self):
        client, sock = self._make_client_with_mock()
        self._mock_response(
            sock,
            {"system_state": "Normal", "proposals_seen": 42, "emergencies": 0},
        )
        status = client.status()
        assert isinstance(status, ConstitutionStatus)
        assert status.system_state == "Normal"
        assert status.proposals_seen == 42

    def test_evaluate(self):
        client, sock = self._make_client_with_mock()
        self._mock_response(
            sock, {"verdict": "Approved", "system_state": "Normal"}
        )
        result = client.evaluate(
            portfolio={"equity": 10000},
            proposal={"asset_id": "BTC"},
        )
        assert result["verdict"] == "Approved"

    def test_recover(self):
        client, sock = self._make_client_with_mock()
        self._mock_response(sock, {"recovery_success": True})
        result = client.recover(cryptographic_proof_valid=True)
        assert result["recovery_success"] is True
