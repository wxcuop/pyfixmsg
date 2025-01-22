import pytest
import socket
import time
import json
import os
from unittest.mock import patch, MagicMock
from pyfixmsg.fixsession import FixInitiator, FixAcceptor, FixMessage

@pytest.fixture
def mock_config(tmp_path):
    config_path = tmp_path / "config.ini"
    config_content = """
    [FIX]
    sender_comp_id = SENDER
    target_comp_id = TARGET
    host = localhost
    port = 5000
    use_tls = False
    heartbeat_interval = 30
    state_file = fix_session_state.json
    """
    config_path.write_text(config_content)
    return config_path

@pytest.fixture
def fix_initiator(mock_config):
    return FixInitiator(config_path=str(mock_config))

@pytest.fixture
def fix_acceptor(mock_config):
    return FixAcceptor(config_path=str(mock_config))

def test_fix_initiator_initialization(fix_initiator):
    assert fix_initiator.sender_comp_id == 'SENDER'
    assert fix_initiator.target_comp_id == 'TARGET'
    assert fix_initiator.host == 'localhost'
    assert fix_initiator.port == 5000
    assert fix_initiator.use_tls is False
    assert fix_initiator.heartbeat_interval == 30

def test_fix_acceptor_initialization(fix_acceptor):
    assert fix_acceptor.sender_comp_id == 'SENDER'
    assert fix_acceptor.target_comp_id == 'TARGET'
    assert fix_acceptor.host == 'localhost'
    assert fix_acceptor.port == 5000
    assert fix_acceptor.use_tls is False
    assert fix_acceptor.heartbeat_interval == 30

def test_fix_initiator_connect(fix_initiator):
    with patch('socket.socket.connect') as mock_connect:
        mock_connect.return_value = None
        fix_initiator.connect()
        assert fix_initiator.connection is not None
        mock_connect.assert_called_once_with(('localhost', 5000))

def test_fix_acceptor_listen(fix_acceptor):
    with patch('socket.socket.bind') as mock_bind, patch('socket.socket.listen') as mock_listen:
        mock_bind.return_value = None
        mock_listen.return_value = None
        fix_acceptor.listen()
        assert fix_acceptor.server_socket is not None
        mock_bind.assert_called_once_with(('localhost', 5000))
        mock_listen.assert_called_once_with(5)

def test_fix_acceptor_accept_connection(fix_acceptor):
    with patch('socket.socket.accept') as mock_accept:
        mock_client_socket = MagicMock()
        mock_accept.return_value = (mock_client_socket, ('localhost', 12345))
        fix_acceptor.listen()
        fix_acceptor.accept_connection()
        assert fix_acceptor.connection == mock_client_socket
        mock_accept.assert_called_once()

def test_fix_initiator_send_message(fix_initiator):
    with patch('socket.socket.sendall') as mock_sendall:
        fix_initiator.connect()
        fix_initiator.sequence_number = 1
        message = FixMessage()
        message.set_field(35, 'D')  # MsgType = New Order - Single
        message.set_field(49, fix_initiator.sender_comp_id)
        message.set_field(56, fix_initiator.target_comp_id)
        message.set_field(34, fix_initiator.sequence_number)
        message.set_field(52, time.strftime('%Y%m%d-%H:%M:%S'))
        fix_initiator.send_message(message)
        assert fix_initiator.sequence_number == 2
        mock_sendall.assert_called_once()

def test_fix_acceptor_receive_message(fix_acceptor):
    mock_data = b'8=FIX.4.2\x019=176\x0135=D\x0149=SENDER\x0156=TARGET\x0134=1\x0152=20230101-12:00:00\x0110=000\x01'
    with patch('socket.socket.recv') as mock_recv:
        mock_recv.return_value = mock_data
        fix_acceptor.listen()
        fix_acceptor.accept_connection()
        received_message = fix_acceptor.connection.recv(1024)
        assert received_message == mock_data
        mock_recv.assert_called_once()

def test_fix_initiator_send_heartbeat(fix_initiator):
    with patch('socket.socket.sendall') as mock_sendall:
        fix_initiator.connect()
        fix_initiator.sequence_number = 1
        fix_initiator.send_heartbeat()
        assert fix_initiator.sequence_number == 2
        mock_sendall.assert_called_once()

def test_fix_initiator_check_heartbeat(fix_initiator):
    with patch('socket.socket.sendall') as mock_sendall:
        fix_initiator.connect()
        fix_initiator.is_logged_on = True
        fix_initiator.last_heartbeat_time = time.time() - 31  # Simulate missed heartbeat
        fix_initiator.check_heartbeat()
        assert fix_initiator.missed_heartbeats == 1
        mock_sendall.assert_called_once()

def test_fix_initiator_send_message_not_connected(fix_initiator):
    with pytest.raises(ConnectionError):
        message = FixMessage()
        message.set_field(35, 'D')  # MsgType = New Order - Single
        fix_initiator.send_message(message)

def test_fix_acceptor_receive_message_not_connected(fix_acceptor):
    with pytest.raises(AttributeError):
        fix_acceptor.connection.recv(1024)

def test_fixsession_save_and_load_state(fix_initiator, tmp_path):
    # Modify sequence number and message store
    fix_initiator.sequence_number = 10
    fix_initiator.message_store = {1: b'message1', 2: b'message2'}
    fix_initiator.save_state()

    # Create a new instance and load the state
    new_fix_initiator = FixInitiator(config_path=str(fix_initiator.config_path))
    new_fix_initiator.load_state()

    assert new_fix_initiator.sequence_number == 10
    assert new_fix_initiator.message_store == {1: b'message1', 2: b'message2'}
