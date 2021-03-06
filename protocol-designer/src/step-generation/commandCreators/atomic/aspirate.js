// @flow
import getNextRobotStateAndWarnings from '../../getNextRobotStateAndWarnings'
import * as errorCreators from '../../errorCreators'
import { getPipetteWithTipMaxVol } from '../../robotStateSelectors'
import type { AspirateParams } from '@opentrons/shared-data/protocol/flowTypes/schemaV3'
import type {
  InvariantContext,
  RobotState,
  CommandCreator,
  CommandCreatorError,
} from '../../types'

/** Aspirate with given args. Requires tip. */
const aspirate = (args: AspirateParams): CommandCreator => (
  invariantContext: InvariantContext,
  prevRobotState: RobotState
) => {
  const { pipette, volume, labware, well, offsetFromBottomMm, flowRate } = args

  const actionName = 'aspirate'
  let errors: Array<CommandCreatorError> = []

  const pipetteSpec = invariantContext.pipetteEntities[pipette]?.spec

  if (!pipetteSpec) {
    errors.push(errorCreators.pipetteDoesNotExist({ actionName, pipette }))
  }

  if (!prevRobotState.tipState.pipettes[pipette]) {
    errors.push(
      errorCreators.noTipOnPipette({
        actionName,
        pipette,
        volume,
        labware,
        well,
      })
    )
  }

  if (errors.length === 0 && pipetteSpec && pipetteSpec.maxVolume < volume) {
    errors.push(
      errorCreators.pipetteVolumeExceeded({
        actionName,
        volume,
        maxVolume: pipetteSpec.maxVolume,
      })
    )
  }

  if (errors.length === 0 && pipetteSpec) {
    const tipMaxVolume = getPipetteWithTipMaxVol(pipette, invariantContext)
    if (tipMaxVolume < volume) {
      errors.push(
        errorCreators.tipVolumeExceeded({
          actionName,
          volume,
          maxVolume: tipMaxVolume,
        })
      )
    }
  }

  if (!labware || !prevRobotState.labware[labware]) {
    errors.push(errorCreators.labwareDoesNotExist({ actionName, labware }))
  }

  if (errors.length > 0) {
    return { errors }
  }

  const commands = [
    {
      command: 'aspirate',
      params: {
        pipette,
        volume,
        labware,
        well,
        offsetFromBottomMm,
        flowRate,
      },
    },
  ]

  return {
    commands,
    ...getNextRobotStateAndWarnings(
      commands[0],
      invariantContext,
      prevRobotState
    ),
  }
}

export default aspirate
