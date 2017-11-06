from ..trackers.pose_tracker import (
    Point, absolute, update, relative, ROOT
)


class Mover:
    def __init__(
        self,
        *,
        driver,
        axis_mapping,
        reference,
        origin=ROOT,
        children=None
    ):
        self._driver = driver
        self._origin = origin
        self._reference = driver if reference is None else reference
        self._parent = None
        self._axis_mapping = axis_mapping
        self._children = children or []
        [child.attach(self) for child in self._children]

    def attach(self, parent):
        self._parent = parent

    def jog(self, pose, axis, distance):
        axis = axis.lower()

        assert axis in 'xyz', "axis value should be x, y or z"

        x, y, z = absolute(pose, self)

        return self.move(
            pose,
            *Point(
                x=x + distance if axis == 'x' else x,
                y=y + distance if axis == 'y' else y,
                z=z + distance if axis == 'z' else z
            )
        )

    def move(self, pose, x, y=0, z=0):
        # Potential users of this method might need less than 3 axis
        if self._parent:
            pose = self._parent.move(pose, x, y, z)

        # apply transformation
        x, y, z = relative(
            pose,
            src=self._origin,
            dst=self._reference,
            src_point=Point(x, y, z))

        driver_target = {}

        if 'x' in self._axis_mapping:
            driver_target[self._axis_mapping['x']] = x
        else:
            x = 0

        if 'y' in self._axis_mapping:
            driver_target[self._axis_mapping['y']] = y
        else:
            y = 0

        if 'z' in self._axis_mapping:
            driver_target[self._axis_mapping['z']] = z
        else:
            z = 0

        self._driver.move(target=driver_target)

        # Update pose with the new value. Since stepper motors are open loop
        # there is no need to to query diver for position
        return update(pose, self, Point(x, y, z))

    def home(self, pose):
        from functools import reduce
        reduce(
            lambda _pose, child: child.home(_pose),
            self._children,
            pose
        )

        position = self._driver.home(axis=''.join(self._axis_mapping.values()))
        # map from driver axis names to xyz and expand position
        # into point object
        point = Point(
            x=position.get(self._axis_mapping.get('x', 'X'), 0.0),
            y=position.get(self._axis_mapping.get('y', 'Y'), 0.0),
            z=position.get(self._axis_mapping.get('z', 'Z'), 0.0)
        )

        return update(pose, self, point)

    def set_speed(self, value):
        pass
        # TODO (artyom 20171105): uncomment once proper plunger speeds are
        # defined
        # self._driver.set_speed({
        #     axis: value
        #     for axis in self._axis_mapping.values()
        # })

    def probe(self, axis, movement):
        axis = axis.lower()

        if self._parent:
            self._parent.probe(axis, movement)

        if axis in self._axis_mapping:
            self._driver.probe_axis(self._axis_mapping[axis], movement)

    def delay(self, seconds):
        self._driver.delay(seconds)
