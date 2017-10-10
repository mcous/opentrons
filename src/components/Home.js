import React from 'react'
import { connect } from 'react-redux'

import { selectors } from '../reducers'
import { openLabwareSelector, closeLabwareSelector, selectLabwareToAdd } from '../actions'
import Deck from './Deck.js'

const ConnectedDeck = connect(
  state => ({
    loadedContainers: selectors.loadedContainers(state),
    canAdd: selectors.canAdd(state),
    modeLabwareSelection: selectors.modeLabwareSelection(state)
  }),
  {
    openLabwareSelector,
    closeLabwareSelector,
    selectLabwareToAdd
  }
)(Deck)

const Home = () => (
  <div>
    <ConnectedDeck />
    <h2>Select labware you wish to add ingredients to</h2>
  </div>
)

export default Home
