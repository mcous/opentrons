'use strict'

// release build steps
// 0. Draft a GitHub release
// 1. Create release branch from `edge` (or if hotfix, `master`), push
// 2. Create release notes branch from `release_*`, push
// 3. Open a PR from `release_*` into `master`
// 4. Open a PR from `notes_*` into `release_*`
// 5. After any PR is merged into `release_*`:
//    a. Tag next alpha
//    b. Overwrite release draft with changelog
//    c. Push tag
// 6. After `release_*` is merged into `master`
//    a. Tag actual release
//    b. Overwrite release draft with final changelog
//    c. Push tag

const assert = require('assert')
const semver = require('semver')
const { getRepoVersionFromGit } = require('./lib/version-utils')

const BUMPS = ['premajor', 'preminor', 'prepatch']

const argv = process.argv.slice(2)
const bump = argv[0]
const identifier = argv[1] || 'alpha'

assert(
  BUMPS.includes(bump),
  `USAGE: start-release <${BUMPS.join('|')}> [identifier=alpha]`
)

getRepoVersionFromGit().then(versionStats => {
  assert(
    versionStats.prerelease.length === 0,
    `ERROR: can't start a release from a prerelease version`
  )

  return semver.parse(semver.inc(versionStats.version, bump, identifier))

  console.log(nextVersion)
})
