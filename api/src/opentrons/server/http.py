import logging
from . import endpoints as endp
from opentrons import config
from .endpoints import (networking, control, settings, update)
from opentrons.deck_calibration import endpoints as dc_endp


from .endpoints import serverlib_fallback as endpoints
log = logging.getLogger(__name__)


class HTTPServer(object):
    def __init__(self, app, log_file_path):
        self.app = app
        self.log_file_path = log_file_path

        self.app.router.add_get(
            '/health', endp.health)
        self.app.router.add_get(
            '/networking/status', networking.status)
        # TODO(mc, 2018-10-12): s/wifi/networking
        self.app.router.add_get(
            '/wifi/list', networking.list_networks)
        self.app.router.add_post(
            '/wifi/configure', networking.configure)
        self.app.router.add_post('/wifi/keys', networking.add_key)
        self.app.router.add_get('/wifi/keys', networking.list_keys)
        self.app.router.add_delete(
            '/wifi/keys/{key_uuid}', networking.remove_key)
        self.app.router.add_get(
            '/wifi/eap-options', networking.eap_options)
        self.app.router.add_post(
            '/identify', control.identify)
        self.app.router.add_get(
            '/modules', control.get_attached_modules)
        self.app.router.add_get(
            '/modules/{serial}/data', control.get_module_data)
        self.app.router.add_post(
            '/modules/{serial}', control.execute_module_command)
        self.app.router.add_post(
            '/camera/picture', control.take_picture)
        self.app.router.add_post(
            '/server/update', endpoints.update_api)
        self.app.router.add_post(
            '/server/update/firmware', endpoints.update_firmware)
        self.app.router.add_post(
            '/modules/{serial}/update', update.update_module_firmware)
        self.app.router.add_get(
            '/update/ignore', endpoints.get_ignore_version)
        self.app.router.add_post(
            '/update/ignore', endpoints.set_ignore_version)

        if config.ARCHITECTURE == config.SystemArchitecture.BUILDROOT:
            from .endpoints import logs
            self.app.router.add_get('/logs/{syslog_identifier}',
                                    logs.get_logs_by_id)
        else:
            self.app.router.add_static(
                '/logs', self.log_file_path, show_index=True)

        self.app.router.add_post(
            '/server/restart', endpoints.restart)
        self.app.router.add_post(
            '/calibration/deck/start', dc_endp.start)
        self.app.router.add_post(
            '/calibration/deck', dc_endp.dispatch)
        self.app.router.add_get(
            '/pipettes', control.get_attached_pipettes)
        self.app.router.add_get(
            '/motors/engaged', control.get_engaged_axes)
        self.app.router.add_post(
            '/motors/disengage', control.disengage_axes)
        self.app.router.add_get(
            '/robot/positions', control.position_info)
        self.app.router.add_post(
            '/robot/move', control.move)
        self.app.router.add_post(
            '/robot/home', control.home)
        self.app.router.add_get(
            '/robot/lights', control.get_rail_lights)
        self.app.router.add_post(
            '/robot/lights', control.set_rail_lights)
        self.app.router.add_get(
            '/settings', settings.get_advanced_settings)
        self.app.router.add_post(
            '/settings', settings.set_advanced_setting)
        self.app.router.add_post(
            '/settings/log_level/local', settings.set_log_level)
        if config.ARCHITECTURE == config.SystemArchitecture.BUILDROOT:
            self.app.router.add_post(
                '/settings/log_level/upstream', logs.set_syslog_level)
        self.app.router.add_post(
            '/settings/reset', settings.reset)
        self.app.router.add_get(
            '/settings/reset/options', settings.available_resets)
        self.app.router.add_get(
            '/settings/pipettes', settings.pipette_settings
        )
        self.app.router.add_get(
            '/settings/pipettes/{id}', settings.pipette_settings_id)
        self.app.router.add_patch(
            '/settings/pipettes/{id}', settings.modify_pipette_settings
        )
