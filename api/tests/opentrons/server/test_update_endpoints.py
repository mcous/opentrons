import os
import json
import tempfile
import asyncio
import pytest
from aiohttp import web
from opentrons.server import init
from opentrons.server.endpoints import update
from opentrons.server.endpoints import serverlib_fallback


async def test_restart(
        virtual_smoothie_env, monkeypatch, async_server, aiohttp_client):
    test_data = {"test": "pass"}
    loop = asyncio.get_event_loop()

    async def mock_restart(request):
        return web.json_response(test_data)

    monkeypatch.setattr(serverlib_fallback, 'restart', mock_restart)
    hw = async_server['com.opentrons.hardware']
    app = init(hw)
    cli = await loop.create_task(aiohttp_client(app))

    expected = json.dumps(test_data)
    resp = await cli.post('/server/restart')
    text = await resp.text()
    assert resp.status == 200
    assert text == expected


@pytest.mark.api1_only
async def test_update(
        virtual_smoothie_env, monkeypatch, async_client, async_server):
    hw = async_server['com.opentrons.hardware']
    msg = "success"
    whl_name = "testy.whl"
    serverlib_name = "testylib.whl"
    fw_name = "testy.fw"
    tmpdir = tempfile.mkdtemp("files")
    for filename in [whl_name, serverlib_name, fw_name]:
        with open(os.path.join(tmpdir, filename), 'w') as fd:
            fd.write("test")

    async def mock_install(filename, loop=None, modeset=True):
        return msg
    monkeypatch.setattr(serverlib_fallback, '_install', mock_install)
    monkeypatch.setattr(hw, 'update_firmware', mock_install)

    cli = async_client

    data = {
        'whl': open(os.path.join(tmpdir, whl_name)),
        'serverlib': open(os.path.join(tmpdir, serverlib_name)),
        'fw': open(os.path.join(tmpdir, fw_name))
    }

    # Note: hits API server update endpoint--this test covers backward
    # compatibility until the update server is universally available
    resp = await cli.post(
        '/server/update',
        data=data)

    expected = json.dumps({
        'message': [msg, msg, msg],
        'filename': [whl_name, serverlib_name, fw_name]
    })
    text = await resp.text()
    assert resp.status == 200
    assert text == expected


async def test_ignore_updates(
        virtual_smoothie_env, loop, aiohttp_client, async_client):
    tmpdir = tempfile.mkdtemp("files")
    ignore_name = "testy_ignore.json"
    serverlib_fallback.filepath = os.path.join(tmpdir, ignore_name)

    cli = async_client
    # Test no ignore file found
    r0 = await cli.get('/update/ignore')
    r0body = await r0.text()
    assert json.loads(r0body) == {'version': None}

    # Test that values are set correctly

    ignore = {'version': '3.1.3'}
    r1 = await cli.post('/update/ignore', json=ignore)
    assert r1.status == 200

    # Test that you cannot pass an empty version
    ignore2 = {'version': ''}
    r2 = await cli.post('/update/ignore', json=ignore2)
    assert r2.status == 400

    # Test that version in the temporary directory is still '3.1.3'
    r3 = await cli.get('/update/ignore')
    r3body = await r3.text()
    assert json.loads(r3body) == {'version': '3.1.3'}


@pytest.mark.api1_only
@pytest.fixture
def dummy_attached_modules(modules):
    temp_module = modules.TempDeck()
    temp_port = 'tty1_tempdeck'
    temp_serial = 'tdYYYYMMDD987'
    temp_module._device_info = {'serial': temp_serial}
    mag_module = modules.MagDeck()
    mag_port = 'tty1_magdeck'
    mag_serial = 'mdYYYYMMDD123'
    mag_module._device_info = {'serial': mag_serial}
    return {
        temp_port + 'tempdeck': temp_module,
        mag_port + 'magdeck': mag_module
    }


async def test_update_module_firmware(
        dummy_attached_modules,
        virtual_smoothie_env,
        loop,
        aiohttp_client,
        monkeypatch,
        async_client,
        async_server,
        modules):

    client = async_client
    hw = async_server['com.opentrons.hardware']
    if async_server['api_version'] == 2:
        hw = hw._api
    serial_num = 'mdYYYYMMDD123'
    fw_filename = 'dummyFirmware.hex'
    tmpdir = tempfile.mkdtemp("files")

    with open(os.path.join(tmpdir, fw_filename), 'wb') as fd:
        fd.write(bytes(0x1234))

    def dummy_discover_modules():
        return

    async def mock_enter_bootloader(module):
        return '/dev/modules/tty0_bootloader'

    monkeypatch.setattr(hw, 'discover_modules', dummy_discover_modules)
    monkeypatch.setattr(hw, '_attached_modules', dummy_attached_modules)
    monkeypatch.setattr(modules, 'enter_bootloader', mock_enter_bootloader)

    # ========= Happy path ==========
    res_msg = {'message': 'Firmware update successful',
               'avrdudeResponse': '1234 bytes of flash verified',
               'filename': fw_filename}

    async def mock_successful_upload_to_module(
            module, fw_file, loop):
        return res_msg

    expected_res = res_msg

    monkeypatch.setattr(modules,
                        'update_firmware', mock_successful_upload_to_module)
    resp = await client.post(
        '/modules/{}/update'.format(serial_num),
        data={'module_firmware': open(os.path.join(tmpdir, fw_filename))})

    assert resp.status == 200
    res = await resp.json()
    assert res == expected_res


async def test_fail_update_module_firmware(
        dummy_attached_modules,
        virtual_smoothie_env,
        monkeypatch,
        async_client,
        async_server,
        modules):

    client = async_client
    hw = async_server['com.opentrons.hardware']
    if async_server['api_version'] == 2:
        hw = hw._api
    serial_num = 'mdYYYYMMDD123'
    fw_filename = 'dummyFirmware.hex'
    tmpdir = tempfile.mkdtemp("files")

    with open(os.path.join(tmpdir, fw_filename), 'wb') as fd:
        fd.write(bytes(0x1234))

    def dummy_discover_modules():
        return

    async def mock_enter_bootloader(module):
        return '/dev/modules/tty0_bootloader'

    monkeypatch.setattr(hw, 'discover_modules', dummy_discover_modules)
    monkeypatch.setattr(hw, '_attached_modules', dummy_attached_modules)
    monkeypatch.setattr(modules, 'enter_bootloader', mock_enter_bootloader)

    # ========= Case 1: Port not accessible =========
    res_msg1 = {'message': 'Firmware update failed',
                'avrdudeResponse': 'ser_open(): can\'t open device',
                'filename': fw_filename}

    async def mock_failed_upload_to_module1(
            serialnum, fw_file, loop):
        return res_msg1

    expected_res1 = res_msg1

    monkeypatch.setattr(modules,
                        'update_firmware', mock_failed_upload_to_module1)
    resp1 = await client.post(
        '/modules/{}/update'.format(serial_num),
        data={'module_firmware': open(os.path.join(tmpdir, fw_filename))})

    assert resp1.status == 500
    j1 = await resp1.json()
    assert j1 == expected_res1

    # ========= Case 2: Corrupted file =========
    res_msg2 = {'message': 'Firmware update failed',
                'avrdudeResponse': 'checksum mismatch in line 1234',
                'filename': fw_filename}

    async def mock_failed_upload_to_module2(
            serialnum, fw_file, loop):
        return res_msg2

    expected_res2 = res_msg2

    monkeypatch.setattr(modules,
                        'update_firmware', mock_failed_upload_to_module2)
    resp2 = await client.post(
        '/modules/{}/update'.format(serial_num),
        data={'module_firmware': open(os.path.join(tmpdir, fw_filename))})

    assert resp2.status == 400
    j2 = await resp2.json()
    assert j2 == expected_res2

    # ========= Case 3: AVRDUDE not responding =========
    expected_res3 = {'message': 'AVRDUDE not responding',
                     'filename': fw_filename}

    async def mock_failed_upload_to_module3(
            serialnum, fw_file, loop):
        await asyncio.sleep(2)

    monkeypatch.setattr(modules,
                        'update_firmware', mock_failed_upload_to_module3)
    update.UPDATE_TIMEOUT = 0.1

    resp3 = await client.post(
        '/modules/{}/update'.format(serial_num),
        data={'module_firmware': open(os.path.join(tmpdir, fw_filename))})

    assert resp3.status == 500
    j3 = await resp3.json()
    assert j3 == expected_res3

    # ========= Case 4: No module/ incorrect serial =========
    wrong_serial = 'abcdef'
    expected_res4 = {'message': 'Module {} not found'.format(wrong_serial),
                     'filename': fw_filename}

    resp4 = await client.post(
        '/modules/{}/update'.format(wrong_serial),
        data={'module_firmware': open(os.path.join(tmpdir, fw_filename))})

    assert resp4.status == 404
    j4 = await resp4.json()
    assert j4 == expected_res4
