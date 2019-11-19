// @flow

import type { RobotApiRequestMeta } from '../robot-api/types'

// common types

export type AttachedPipette = $ReadOnly<{|
  id: string,
  name: string,
  model: string,
  tip_length: number,
  mount_axis: string,
  plunger_axis: string,
|}>

export type AttachedPipettesByMount = $ReadOnly<{|
  left: null | AttachedPipette,
  right: null | AttachedPipette,
|}>

// action types

// fetch pipettes

export type FetchPipettesAction = {|
  type: 'pipettes:FETCH_PIPETTES',
  payload: {| robotName: string, refresh: boolean |},
  meta: RobotApiRequestMeta,
|}

export type FetchPipettesSuccessAction = {|
  type: 'pipettes:FETCH_PIPETTES_SUCCESS',
  payload: {| robotName: string, pipettes: AttachedPipettesByMount |},
  meta: RobotApiRequestMeta,
|}

export type FetchPipettesFailureAction = {|
  type: 'pipettes:FETCH_PIPETTES_FAILURE',
  payload: {| robotName: string, error: {} |},
  meta: RobotApiRequestMeta,
|}

export type FetchPipettesDoneAction =
  | FetchPipettesSuccessAction
  | FetchPipettesFailureAction

// pipette actions union

export type PipettesAction =
  | FetchPipettesAction
  | FetchPipettesSuccessAction
  | FetchPipettesFailureAction

// state types

export type PerRobotPipettesState = $ReadOnly<{|
  attachedByMount: AttachedPipettesByMount,
|}>

export type PipettesState = $Shape<
  $ReadOnly<{|
    [robotName: string]: void | PerRobotPipettesState,
  |}>
>

// API response types

export type FetchPipettesResponsePipette =
  | AttachedPipette
  | {|
      id: null,
      name: null,
      model: null,
      mount_axis: string,
      plunger_axis: string,
    |}

export type FetchPipettesResponseBody = {|
  left: FetchPipettesResponsePipette,
  right: FetchPipettesResponsePipette,
|}