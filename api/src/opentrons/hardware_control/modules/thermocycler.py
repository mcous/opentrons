import asyncio
from . import mod_abc, types
from typing import Union, Optional, List, Callable
from opentrons.drivers.thermocycler.driver import (
    Thermocycler as ThermocyclerDriver)
import logging

MODULE_LOG = logging.getLogger(__name__)


class SimulatingDriver:
    def __init__(self):
        self._target_temp = None
        self._ramp_rate = None
        self._hold_time = None
        self._active = False
        self._port = None
        self._lid_status = 'open'
        self._lid_target = None
        self._lid_heating_active = False

    async def open(self):
        # TODO: BC 2019-07-11 once safe threshold is established in
        # firmware, handle UI level warning responsibly here

        # if self._active:
        #     raise ThermocyclerError(
        #         'Cannot open Thermocycler while it is active')
        self._lid_status = 'open'
        return self._lid_status

    async def close(self):
        self._lid_status = 'closed'
        return self._lid_status

    @property
    def status(self):
        return 'holding at target' if self._active else 'idle'

    @property
    def lid_status(self):
        return self._lid_status

    @property
    def ramp_rate(self):
        return self._ramp_rate

    @property
    def hold_time(self):
        # Simulating driver acts as if cycles end immediately
        return 0

    @property
    def temperature(self):
        return self._target_temp

    @property
    def target(self):
        return self._target_temp

    @property
    def lid_target(self):
        return self._lid_target

    @property
    def lid_temp_status(self):
        return 'holding at target' if self._lid_heating_active else 'idle'

    @property
    def lid_temp(self):
        return self._lid_target

    async def connect(self, port):
        self._port = port

    def disconnect(self):
        self._port = None

    async def set_temperature(self,
                              temp: float,
                              hold_time: float,
                              ramp_rate: float) -> None:
        self._target_temp = temp
        self._hold_time = hold_time
        self._ramp_rate = ramp_rate
        self._active = True

    async def set_lid_temperature(self, temp: Optional[float]):
        """ Set the lid temperature in deg Celsius """
        self._lid_heating_active = True
        self._lid_target = temp

    async def stop_lid_heating(self):
        self._lid_heating_active = False
        self._lid_target = None

    async def deactivate(self):
        self._target_temp = None
        self._ramp_rate = None
        self._hold_time = None
        self._active = None
        self._lid_heating_active = False
        self._lid_target = None

    async def get_device_info(self):
        return {'serial': 'dummySerial',
                'model': 'dummyModel',
                'version': 'dummyVersion'}


class Thermocycler(mod_abc.AbstractModule):
    """
    Under development. API subject to change without a version bump
    """
    @classmethod
    async def build(cls,
                    port: str,
                    interrupt_callback: mod_abc.InterruptCallback,
                    simulating: bool = False,
                    loop: asyncio.AbstractEventLoop = None):
        """Build and connect to a Thermocycler
        """

        mod = cls(port, interrupt_callback, simulating, loop)
        await mod._connect()
        return mod

    @classmethod
    def name(cls):
        return 'thermocycler'

    @classmethod
    def display_name(cls):
        return 'Thermocycler'

    @staticmethod
    def _build_driver(
            simulating: bool,
            interrupt_cb: Callable[[str], None] = None)\
            -> Union['SimulatingDriver', 'ThermocyclerDriver']:
        if simulating:
            return SimulatingDriver()
        else:
            return ThermocyclerDriver(interrupt_cb)

    def __init__(self,
                 port: str,
                 interrupt_callback: mod_abc.InterruptCallback = None,
                 simulating: bool = False,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        self._interrupt_cb = interrupt_callback
        self._driver = self._build_driver(simulating, interrupt_callback)

        if None is loop:
            self._loop = asyncio.get_event_loop()
        else:
            self._loop = loop

        self._port = port
        self._device_info = None
        self._poller = None

        self._running_flag = asyncio.Event(loop=self._loop)
        self._current_cycle_task: Optional[asyncio.Task] = None

        self._total_cycle_count: Optional[int] = None
        self._current_cycle_index: Optional[int] = None
        self._total_step_count: Optional[int] = None
        self._current_step_index: Optional[int] = None

    def pause(self):
        self._loop.call_soon_threadsafe(self._running_flag.clear)

    def resume(self):
        self._loop.call_soon_threadsafe(self._running_flag.set)

    def cancel(self):
        if self._current_cycle_task:
            self._current_cycle_task.cancel()
            self._current_cycle_task = None
            self._loop.call_soon_threadsafe(self._running_flag.clear)

    async def deactivate(self):
        self._total_cycle_count = None
        self._current_cycle_index = None
        self._total_step_count = None
        self._current_step_index = None
        await self._driver.deactivate()

    async def open(self) -> str:
        """ Open the lid if it is closed"""
        return await self._driver.open()

    async def close(self) -> str:
        """ Close the lid if it is open"""
        return await self._driver.close()

    async def set_temperature(self, temperature,
                              hold_time_seconds: float = None,
                              hold_time_minutes: float = None,
                              ramp_rate=None):
        seconds = hold_time_seconds if hold_time_seconds is not None else 0
        minutes = hold_time_minutes if hold_time_minutes is not None else 0
        total_seconds = seconds + (minutes * 60)
        hold_time = total_seconds if total_seconds > 0 else 0
        await self._driver.set_temperature(
            temp=temperature, hold_time=hold_time, ramp_rate=ramp_rate)
        if hold_time:
            await self.wait_for_hold()
        else:
            await self.wait_for_temp()

    async def _execute_cycles(self,
                              steps: List[types.ThermocyclerStep],
                              repetitions: int):
        for rep in range(repetitions):
            self._current_cycle_index = rep + 1  # science starts at 1
            for step_idx, step in enumerate(steps):
                await self._running_flag.wait()
                self._current_step_index = step_idx + 1  # science starts at 1
                await self.set_temperature(**step)
                await self.wait_for_hold()

    async def cycle_temperatures(self,
                                 steps: List[types.ThermocyclerStep],
                                 repetitions: int):
        self._running_flag.set()
        self._total_cycle_count = repetitions
        self._total_step_count = len(steps)
        cycle_task = self._loop.create_task(self._execute_cycles(steps,
                                                                 repetitions))
        self._current_cycle_task = cycle_task
        await cycle_task

    async def set_lid_temperature(self, temp: float):
        """ Set the lid temperature in deg Celsius """
        await self._driver.set_lid_temperature(temp=temp)
        await self.wait_for_lid_temp()

    async def stop_lid_heating(self):
        return await self._driver.stop_lid_heating()

    async def wait_for_lid_temp(self):
        """
        This method only exits if lid target temperature has been reached.

        Subject to change without a version bump.
        """
        while self._driver.lid_temp_status != 'holding at target':
            await asyncio.sleep(0.1)

    async def wait_for_temp(self):
        """
        This method only exits if set temperature has been reached.

        Subject to change without a version bump.
        """
        while self.status != 'holding at target':
            await asyncio.sleep(0.1)

    async def wait_for_hold(self):
        """
        This method returns only when hold time has elapsed
        """
        while self.hold_time != 0:
            await asyncio.sleep(0.1)

    @property
    def lid_target(self):
        return self._driver.lid_target

    @property
    def lid_temp(self):
        return self._driver.lid_temp

    @property
    def lid_status(self):
        return self._driver.lid_status

    @property
    def lid_temp_status(self):
        return self._driver.lid_temp_status

    @property
    def ramp_rate(self):
        return self._driver.ramp_rate

    @property
    def hold_time(self):
        return self._driver.hold_time

    @property
    def temperature(self):
        return self._driver.temperature

    @property
    def target(self):
        return self._driver.target

    @property
    def status(self):
        return self._driver.status

    @property
    def device_info(self):
        return self._device_info

    @property
    def total_cycle_count(self):
        return self._total_cycle_count

    @property
    def current_cycle_index(self):
        return self._current_cycle_index

    @property
    def total_step_count(self):
        return self._total_step_count

    @property
    def current_step_index(self):
        return self._current_step_index

    @property
    def live_data(self):
        return {
            'status': self.status,
            'data': {
                'lid': self.lid_status,
                'lidTarget': self.lid_target,
                'lidTemp': self.lid_temp,
                'currentTemp': self.temperature,
                'targetTemp': self.target,
                'holdTime': self.hold_time,
                'rampRate': self.ramp_rate,
                'currentCycleIndex': self.current_cycle_index,
                'totalCycleCount': self.total_cycle_count,
                'currentStepIndex': self.current_step_index,
                'totalStepCount': self.total_step_count,
            }
        }

    @property
    def is_simulated(self):
        return isinstance(self._driver, SimulatingDriver)

    @property
    def interrupt_callback(self):
        """ Fetch the current interrupt callback

        Exposes the interrupt callback used with the TCPoller, so it can be re-
        hooked in the new module instance after a firmware update.
        """
        return self._interrupt_cb

    @property
    def loop(self):
        return self._loop

    def set_loop(self, newLoop):
        self._loop = newLoop
        self._running_flag = asyncio.Event(loop=self._loop)

    async def _connect(self):
        await self._driver.connect(self._port)
        self._device_info = await self._driver.get_device_info()

    @property
    def port(self):
        return self._port

    async def prep_for_update(self):
        pass
