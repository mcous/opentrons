// @flow
import * as React from 'react'
import { Formik, Form, Field } from 'formik'
import { OutlineButton } from '@opentrons/components'
import TempField from './TempField'

import styles from './styles.css'

import type { ModuleCommandRequest } from '../../robot-api'

type Props = {
  setTemp: (request: ModuleCommandRequest) => mixed,
}

export default class TemperatureControls extends React.Component<Props> {
  inputRef: { current: null | HTMLInputElement }

  constructor(props: Props) {
    super(props)
    this.inputRef = React.createRef()
  }

  deactivateModule = () => {
    this.props.setTemp({ command_type: 'deactivate' })
  }

  render() {
    return (
      <Formik
        initialValues={{ target: '' }}
        onSubmit={(values, actions) => {
          const target = values.target === '' ? null : Number(values.target)
          if (!target) {
            return
          }
          const request = {
            command_type: 'set_temperature',
            args: [target],
          }
          this.props.setTemp(request)

          const $input = this.inputRef.current
          if ($input) $input.blur()

          actions.resetForm()
        }}
        render={formProps => {
          return (
            <Form className={styles.temperature_form}>
              <Field name="target" component={TempField} />
              <OutlineButton type="submit" className={styles.set_button}>
                Set target
              </OutlineButton>
              <OutlineButton
                className={styles.set_button}
                onClick={this.deactivateModule}
              >
                Deactivate
              </OutlineButton>
            </Form>
          )
        }}
      />
    )
  }
}
