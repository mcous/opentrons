'use strict'

const Promise = require('bluebird')
const assert = require('assert')
const path = require('path')
const readJson = require('load-json-file')
const writeJson = require('write-json-file')
const semver = require('semver')
const { zipObject } = require('lodash')
const { gitDescribe } = require('git-describe')
const { workspaces } = require('../../package.json')

const argv = process.argv.slice(2)

const dryrun = !argv.includes('--write')

const packageFiles = workspaces.map(w =>
  path.join(__dirname, '../..', w, 'package.json')
)

const getPackages = Promise.map(packageFiles, file => readJson(file))
const getRepoVersion = gitDescribe({ match: 'v*.*.*' }).then(gitDescToVersion)

Promise.join(getRepoVersion, getPackages, (repoVersion, packages) => {
  const names = packages.map(p => p.name)
  const getVersions = Promise.map(names, packageNameToVersion)

  return getVersions
    .then(versions => zipObject(names, versions))
    .then(versionMap => {
      console.log(versionMap)

      return packageFiles.map((filename, i) => {
        const pkg = packages[i]
        const { name, dependencies, devDependencies } = pkg
        const updates = { version: versionMap[name] }

        if (dependencies) {
          updates.dependencies = updateDependencies(dependencies, versionMap)
        }

        if (devDependencies) {
          updates.devDependencies = updateDependencies(
            devDependencies,
            versionMap
          )
        }

        return [filename, Object.assign({}, pkg, updates)]
      })
    })
    .then(packageUpdates => {
      return Promise.each(packageUpdates, ([filename, pkg]) => {
        console.log(
          `${dryrun ? 'DRYRUN ' : ''}Updating ${filename} to ${pkg.version}`
        )

        if (!dryrun) {
          return writeJson(filename, pkg, { indent: '  ' })
        }
      })
    })
})

function packageNameToVersion(name) {
  const projectName = name.replace(/^@opentrons\//, '')
  const getProjectGitDesc = gitDescribe({ match: `${projectName}@*.*.*` })

  return Promise.join(
    getRepoVersion,
    getProjectGitDesc,
    (repoVersion, projectDesc) => {
      return projectDesc.tag ? gitDescToVersion(projectDesc) : repoVersion
    }
  )
}

function gitDescToVersion(gitDesc) {
  assert(gitDesc.tag, `ERROR: failed to find a valid tag`)

  const version = semver.coerce(gitDesc.tag)
  const suffix = gitDesc.distance ? `+${gitDesc.suffix.replace(/-/g, '.')}` : ''

  return `${version}${suffix}`
}

function updateDependencies(dependencies, versionMap) {
  return Object.keys(dependencies).reduce((deps, name) => {
    if (versionMap[name]) {
      return Object.assign({}, deps, { [name]: versionMap[name] })
    }
    return deps
  }, dependencies)
}
