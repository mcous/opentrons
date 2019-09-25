import pytest

from tests.opentrons.conftest import state, log_by_axis

from numpy import isclose, subtract
from opentrons.trackers import pose_tracker


@pytest.fixture
def smoke(robot):
    robot.connect()
    robot.reset()
    robot.home()
    robot._driver.log.clear()
    from tests.opentrons.data import smoke  # NOQA


def test_smoke(virtual_smoothie_env, smoke, robot):
    by_axis = log_by_axis(robot._driver.log, 'XYA')
    coords = [
        (x, y, z)
        for x, y, z
        in zip(by_axis['X'], by_axis['Y'], by_axis['A'])
    ]
    assert coords


@pytest.mark.api1_only
@pytest.mark.parametrize('protocol_file', ['multi-single.py'])
async def test_multi_single(
        main_router, protocol, protocol_file, dummy_db, robot):
    robot.connect()
    robot.home()
    session = main_router.session_manager.create(
        name='<blank>', text=protocol.text)

    await main_router.wait_until(state('session', 'loaded'))

    main_router.calibration_manager.move_to(
        session.instruments[0],
        session.containers[2])


@pytest.mark.api1_only
@pytest.mark.parametrize('protocol_file', ['multi-single.py'])
async def test_load_jog_save_run(
        main_router, protocol, protocol_file, dummy_db, monkeypatch, robot):
    import tempfile
    temp = tempfile.gettempdir()
    monkeypatch.setenv('USER_DEFN_ROOT', temp)

    session = main_router.session_manager.create(
        name='<blank>', text=protocol.text)
    await main_router.wait_until(state('session', 'loaded'))

    main_router.calibration_manager.move_to_front(session.instruments[0])
    await main_router.wait_until(state('calibration', 'ready'))

    main_router.calibration_manager.tip_probe(session.instruments[0])
    await main_router.wait_until(state('calibration', 'ready'))

    def instrument_procedure(index):
        def position(instrument):
            return pose_tracker.absolute(
                robot.poses,
                instrument._instrument
            )

        main_router.calibration_manager.move_to(
            session.instruments[index],
            session.containers[0])

        pos = position(session.instruments[index])

        acc = []
        for axis in 'xyz':
            main_router.calibration_manager.jog(
                session.instruments[index],
                1.0,
                axis
            )
            acc.append(subtract(position(session.instruments[index]), pos))

        assert isclose(acc[0], [1.0, 0.0, 0.0]).all()
        assert isclose(acc[1], [1.0, 1.0, 0.0]).all()
        assert isclose(acc[2], [1.0, 1.0, 1.0]).all()

        pos = position(session.instruments[index])

        main_router.calibration_manager.update_container_offset(
            container=session.containers[0],
            instrument=session.instruments[index])

        # TODO (artyom 20171011): move home to a proper API endpoint
        robot.home()

        main_router.calibration_manager.move_to(
            session.instruments[index],
            session.containers[0])

        # Last position should correspond to the value when
        # 'update_container_offset' was called
        assert isclose(pos, position(session.instruments[index])).all()

    instrument_procedure(1)
    instrument_procedure(0)
