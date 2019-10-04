'use strict'

const assert = require('assert')
const path = require('path')
const semver = require('semver')
const { gitDescribe } = require('git-describe')

const REPO_ROOT = path.join(__dirname, '../../..')

function getRepoVersionFromGit() {
  return gitDescribe(REPO_ROOT, { match: 'v*.*.*' }).then(gitDescToVersion)
}

function gitDescToVersion(gitDesc) {
  assert(gitDesc.tag, `ERROR: failed to find a valid tag`)

  const version = semver.coerce(gitDesc.tag)
  const suffix = gitDesc.distance ? `+${gitDesc.suffix.replace(/-/g, '.')}` : ''

  return semver.parse(`${version}${suffix}`)
}

module.exports = { REPO_ROOT, getRepoVersionFromGit, gitDescToVersion }
