import json
from copy import deepcopy

import pytest

from opentrons import types
from opentrons.legacy_api import modules as legacy_modules

from opentrons.drivers.smoothie_drivers.driver_3_0 import SmoothieDriver_3_0_0
from opentrons.hardware_control import modules
from opentrons.config import pipette_config


async def test_get_pipettes_uncommissioned(
        async_server, loop, async_client, monkeypatch):

    expected = {
        "left": {
            "mount_axis": "z",
            "plunger_axis": "b",
            "model": None,
            "name": None,
            "id": None
        },
        "right": {
            "mount_axis": "a",
            "plunger_axis": "c",
            "model": None,
            "name": None,
            "id": None
        }
    }

    if async_server['api_version'] == 1:
        def mock_parse_fail(gcode, mount):
            pass

        def fake_update_config(axis, data):
            pass

        def fake_update_steps_per_mm(data):
            pass

        monkeypatch.setattr(
            async_server['com.opentrons.hardware']._driver,
            '_read_from_pipette', mock_parse_fail)
        monkeypatch.setattr(
            async_server['com.opentrons.hardware']._driver,
            'update_pipette_config', fake_update_config)
        monkeypatch.setattr(
            async_server['com.opentrons.hardware']._driver,
            'update_steps_per_mm', fake_update_steps_per_mm)
        hw = async_server['com.opentrons.hardware']
        hw._driver.simulating = False

    else:
        hw = async_server['com.opentrons.hardware']._backend
        hw._attached_instruments[types.Mount.LEFT] = {
            'model': None, 'id': None}

    resp = await async_client.get('/pipettes?refresh=true')
    if async_server['api_version'] == 1:
        hw._driver.simulating = True
    text = await resp.text()
    assert resp.status == 200
    assert json.loads(text) == expected


async def test_get_pipettes(async_server, async_client, monkeypatch):
    test_model = 'p300_multi_v1'
    test_name = 'p300_multi'
    test_id = '123abc'

    hw = async_server['com.opentrons.hardware']
    if async_server['api_version'] == 1:
        def dummy_read_model(mount):
            return test_model

        def dummy_read_id(mount):
            return test_id

        monkeypatch.setattr(
            hw._driver, 'read_pipette_model', dummy_read_model)
        monkeypatch.setattr(
            hw._driver, 'read_pipette_id', dummy_read_id)
    else:
        hw._backend._attached_instruments = {
            types.Mount.RIGHT: {'model': test_model, 'id': test_id},
            types.Mount.LEFT: {'model': test_model, 'id': test_id}
        }

    model = pipette_config.load(test_model)
    expected = {
        'left': {
            'model': test_model,
            'name': test_name,
            'tip_length': model.tip_length,
            'mount_axis': 'z',
            'plunger_axis': 'b',
            'id': test_id
        },
        'right': {
            'model': test_model,
            'name': test_name,
            'tip_length': model.tip_length,
            'mount_axis': 'a',
            'plunger_axis': 'c',
            'id': test_id
        }
    }

    resp = await async_client.get('/pipettes?refresh=true')
    text = await resp.text()
    assert resp.status == 200
    assert json.loads(text) == expected


@pytest.mark.api2_only
async def test_get_modules_v2(
        async_server, loop, async_client, monkeypatch):
    hw = async_server['com.opentrons.hardware']
    monkeypatch.setattr(hw._backend,
                        '_attached_modules',
                        [('/dev/modules/tty1_magdeck', 'magdeck')])
    await check_modules_response(async_client)


@pytest.mark.api1_only
async def test_get_modules_v1(
        virtual_smoothie_env, loop, async_client, monkeypatch):

    def stub_discover():
        return [('tty1_magdeck', 'magdeck')]

    monkeypatch.setattr(legacy_modules, "discover", stub_discover)
    await check_modules_response(async_client)


async def check_modules_response(async_client):
    keys = sorted(['name', 'port', 'serial', 'model', 'fwVersion',
                   'displayName', 'status', 'data'])
    resp = await async_client.get('/modules')
    body = await resp.json()
    assert resp.status == 200
    assert 'modules' in body
    assert len(body['modules']) == 1
    assert sorted(body['modules'][0].keys()) == keys
    assert 'engaged' in body['modules'][0]['data']


@pytest.fixture
async def dummy_discover_modules():
    mag_module = await modules.build('', 'magdeck', True, lambda x: None)

    async def stub():
        return [mag_module]
    return stub


@pytest.fixture
def dummy_attached_leg_modules():
    mag_module = legacy_modules.MagDeck()
    mag_port = 'tty1_magdeck'
    mag_serial = 'mdYYYYMMDD123'
    mag_module._device_info = {'serial': mag_serial}
    return {
        mag_port + 'magdeck': mag_module
    }


@pytest.mark.api2_only
async def test_execute_module_command_v2(
          dummy_discover_modules,
          virtual_smoothie_env,
          loop,
          async_server,
          async_client,
          monkeypatch):
    hw = async_server['com.opentrons.hardware']

    def dummy_get_attached_modules():
        return []

    monkeypatch.setattr(hw, 'discover_modules', dummy_discover_modules)

    resp = await async_client.post('/modules/dummySerial',
                                   json={'command_type': 'deactivate'})
    body = await resp.json()
    assert resp.status == 200
    assert 'message' in body
    assert body['message'] == 'Success'


@pytest.mark.api1_only
async def test_execute_module_command_v1(
          dummy_attached_leg_modules,
          virtual_smoothie_env,
          loop,
          async_server,
          async_client,
          monkeypatch):
    hw = async_server['com.opentrons.hardware']
    monkeypatch.setattr(hw, '_attached_modules', dummy_attached_leg_modules)

    resp = await async_client.post('/modules/mdYYYYMMDD123',
                                   json={'command_type': 'disengage'})
    body = await resp.json()
    assert resp.status == 200
    assert 'message' in body
    assert body['message'] == 'Success'


async def test_get_cached_pipettes(async_server, async_client, monkeypatch):
    test_model = 'p300_multi_v1'
    test_name = 'p300_multi'
    test_id = '123abc'

    hw = async_server['com.opentrons.hardware']
    if async_server['api_version'] == 1:
        def dummy_read_model(mount):
            return test_model

        def dummy_read_id(mount):
            return test_id

        monkeypatch.setattr(
            hw._driver, 'read_pipette_model', dummy_read_model)
        monkeypatch.setattr(
            hw._driver, 'read_pipette_id', dummy_read_id)
    else:
        hw._backend._attached_instruments = {
            types.Mount.RIGHT: {'model': test_model, 'id': test_id},
            types.Mount.LEFT: {'model': test_model, 'id': test_id}
        }

    if async_server['api_version'] == 1:
        hw.reset()
    else:
        await hw.reset()

    model = pipette_config.load(test_model)
    expected = {
        'left': {
            'model': test_model,
            'name': test_name,
            'tip_length': model.tip_length,
            'mount_axis': 'z',
            'plunger_axis': 'b',
            'id': test_id
        },
        'right': {
            'model': test_model,
            'name': test_name,
            'tip_length': model.tip_length,
            'mount_axis': 'a',
            'plunger_axis': 'c',
            'id': test_id
        }
    }

    resp = await async_client.get('/pipettes')
    text = await resp.text()
    assert resp.status == 200
    assert json.loads(text) == expected

    model1 = 'p10_single_v1.3'
    config1 = pipette_config.load(model1)
    id1 = 'fgh876'
    if async_server['api_version'] == 1:
        def dummy_read_model(mount):
            return model1

        def dummy_read_id(mount):
            return id1

        monkeypatch.setattr(
            hw._driver, 'read_pipette_model', dummy_read_model)
        monkeypatch.setattr(
            hw._driver, 'read_pipette_id', dummy_read_id)
    else:
        hw._backend._attached_instruments = {
            types.Mount.RIGHT: {'model': model1, 'id': id1},
            types.Mount.LEFT: {'model': model1, 'id': id1}
        }

    resp1 = await async_client.get('/pipettes')
    text1 = await resp1.text()
    assert resp1.status == 200
    assert json.loads(text1) == expected

    expected2 = {
        'left': {
            'model': model1,
            'name': pipette_config.name_for_model(model1),
            'tip_length': config1.tip_length,
            'mount_axis': 'z',
            'plunger_axis': 'b',
            'id': id1
        },
        'right': {
            'model': model1,
            'name': pipette_config.name_for_model(model1),
            'tip_length': config1.tip_length,
            'mount_axis': 'a',
            'plunger_axis': 'c',
            'id': id1
        }
    }

    resp2 = await async_client.get('/pipettes?refresh=true')
    text2 = await resp2.text()
    assert resp2.status == 200
    assert json.loads(text2) == expected2


async def test_disengage_axes(async_client, monkeypatch):
    def mock_send(self, command, timeout=None):
        pass

    monkeypatch.setattr(
        SmoothieDriver_3_0_0, '_send_command', mock_send)

    alltrue = {
        "x": {"enabled": True},
        "y": {"enabled": True},
        "z": {"enabled": True},
        "a": {"enabled": True},
        "b": {"enabled": True},
        "c": {"enabled": True}}
    res0 = await async_client.get('/motors/engaged')
    result0 = await res0.text()
    assert res0.status == 200
    assert json.loads(result0) == alltrue

    postres = await async_client.post(
        '/motors/disengage', json={'axes': ['X', 'b']})
    assert postres.status == 200

    xbfalse = deepcopy(alltrue)
    xbfalse["x"]["enabled"] = False
    xbfalse["b"]["enabled"] = False
    res1 = await async_client.get('/motors/engaged')
    result1 = await res1.text()
    assert res1.status == 200
    assert json.loads(result1) == xbfalse

    resp = await async_client.post('/robot/home',
                                   json={'target': 'robot'})
    assert resp.status == 200
    res2 = await async_client.get('/motors/engaged')
    result2 = await res2.text()
    assert res2.status == 200
    assert json.loads(result2) == alltrue


async def test_robot_info(async_client):
    res = await async_client.get('/robot/positions')
    assert res.status == 200

    text = await res.text()
    body = json.loads(text)
    assert body['positions']['change_pipette']['target'] == 'mount'
    assert len(body['positions']['change_pipette']['left']) == 3
    assert len(body['positions']['change_pipette']['right']) == 3
    assert body['positions']['attach_tip']['target'] == 'pipette'
    assert len(body['positions']['attach_tip']['point']) == 3


async def test_home_pipette(async_client):
    test_data = {
        'target': 'pipette',
        'mount': 'left'}

    res = await async_client.post('/robot/home', json=test_data)
    assert res.status == 200

    res2 = await async_client.post('/robot/home', json=test_data)
    assert res2.status == 200


async def test_instrument_reuse(async_server, async_client, monkeypatch):
    hw = async_server['com.opentrons.hardware']

    # With no pipette connected before homing pipettes, we should a) not crash
    # and b) not have any instruments connected afterwards

    test_data = {
        'target': 'pipette',
        'mount': 'left'
    }

    res = await async_client.post('/robot/home', json=test_data)
    assert res.status == 200

    res = await async_client.get('/pipettes')
    data = await res.json()
    assert data['left']['model'] is None

    # If we do have a pipette connected, if we home we should still have it
    # connected afterwards
    test_model = 'p300_multi_v1'
    if async_server['api_version'] == 1:
        from opentrons import instruments

        def dummy_read_model(mount):
            return test_model

        monkeypatch.setattr(hw._driver, 'read_pipette_model', dummy_read_model)
        instruments.P300_Multi('left')
    else:
        hw._backend._attached_instruments = {
            types.Mount.RIGHT: {'model': test_model, 'id': 'dummy-id'},
            types.Mount.LEFT: {'model': test_model, 'id': 'dummy-id'}
        }

    res = await async_client.get('/pipettes',
                                 params=[('refresh', 'true')])
    data = await res.json()
    assert data['left']['model'] == test_model

    res = await async_client.post('/robot/home', json=test_data)
    assert res.status == 200

    res = await async_client.get('/pipettes')
    data = await res.json()

    assert data['left']['model'] == test_model


async def test_home_robot(async_client):
    test_data = {
        'target': 'robot'}

    res = await async_client.post('/robot/home', json=test_data)

    assert res.status == 200


async def test_home_pipette_bad_request(async_client):
    test_data = {}
    res = await async_client.post('/robot/home', json=test_data)

    assert res.status == 400

    test_data_2 = {
        'target': 'pipette',
        'mount': 'fake_mount'}

    res2 = await async_client.post('/robot/home', json=test_data_2)

    assert res2.status == 400

    test_data_3 = {
        'mount': 'left'}

    res3 = await async_client.post('/robot/home', json=test_data_3)

    assert res3.status == 400

    test_data_4 = {
        'target': 'pipette'}

    res4 = await async_client.post('/robot/home', json=test_data_4)

    assert res4.status == 400


async def test_move_bad_request(async_client):
    data0 = {
        'target': 'other'
    }
    res = await async_client.post('/robot/move', json=data0)
    assert res.status == 400

    data1 = {
        'target': 'mount',
        'point': (1, 2, 3, 4)
    }
    res = await async_client.post('/robot/move', json=data1)
    assert res.status == 400

    data2 = {
        'target': 'mount',
        'point': (1, 2, 3),
        'mount': 'middle'
    }
    res = await async_client.post('/robot/move', json=data2)
    assert res.status == 400

    data3 = {
        'target': 'pipette',
        'point': (1, 2, 3),
        'mount': 'left',
        'model': 'p9000+'
    }
    res = await async_client.post('/robot/move', json=data3)
    assert res.status == 400


async def test_move_mount(async_client):
    resp = await async_client.post('/robot/home',
                                   json={'target': 'robot'})
    assert resp.status == 200
    data = {
        'target': 'mount',
        'point': [100, 200, 50],
        'mount': 'right'
    }
    res = await async_client.post('/robot/move', json=data)
    assert res.status == 200


async def test_move_pipette(async_client):
    resp = await async_client.post('/robot/home',
                                   json={'target': 'robot'})
    assert resp.status == 200
    data = {
        'target': 'pipette',
        'point': [100, 200, 50],
        'mount': 'right',
        'model': 'p300_single_v1'
    }
    res = await async_client.post('/robot/move', json=data)
    assert res.status == 200


async def test_move_and_home_existing_pipette(async_server, async_client):
    hw = async_server['com.opentrons.hardware']
    if async_server['api_version'] == 1:
        hw.reset()
    else:
        await hw.reset()
    resp = await async_client.post('/robot/home', json={'target': 'robot'})
    assert resp.status == 200
    if async_server['api_version'] == 1:
        from opentrons import instruments
        instruments.P300_Single(mount='right')
    move_data = {
        'target': 'pipette',
        'point': [100, 200, 50],
        'mount': 'right',
        'model': 'p300_single_v1'
    }
    res = await async_client.post('/robot/move', json=move_data)
    assert res.status == 200

    move_data = {
        'target': 'pipette',
        'mount': 'right'
    }
    res1 = await async_client.post('/robot/home', json=move_data)
    assert res1.status == 200


@pytest.mark.api2_only
async def test_rail_lights(async_client):
    resp = await async_client.get('/robot/lights')
    assert resp.status == 200
    data = await resp.json()
    assert not data['on']

    resp = await async_client.post('/robot/lights',
                                   json={'on': True})
    assert resp.status == 200
    data = await resp.json()
    assert data['on']

    resp = await async_client.get('/robot/lights')
    assert resp.status == 200
    data = await resp.json()
    assert data['on']

    resp = await async_client.post('/robot/lights',
                                   json={'on': False})
    assert resp.status == 200
    data = await resp.json()
    assert not data['on']

    resp = await async_client.get('/robot/lights')
    assert resp.status == 200
    data = await resp.json()
    assert not data['on']
