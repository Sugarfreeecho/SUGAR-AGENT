/** Allow audio capture only for the main SugarAgent page on its loopback origin. */
function installSpeechPermissions(contents, resolveOrigin) {
  const uiPermissions = new Set(['clipboard-sanitized-write', 'fullscreen'])
  function trusted(candidate, details) {
    if (candidate !== contents || !details || details.isMainFrame !== true) return false
    try {
      return new URL(details.requestingUrl || details.requestingOrigin || contents.getURL()).origin === resolveOrigin()
    } catch { return false }
  }
  contents.session.setPermissionCheckHandler((candidate, permission, origin, details) => {
    if (permission !== 'media') return uiPermissions.has(permission)
      && trusted(candidate, { ...details, requestingOrigin: origin })
    return trusted(candidate, { ...details, requestingOrigin: origin })
      && details?.mediaType === 'audio'
  })
  contents.session.setPermissionRequestHandler((candidate, permission, callback, details) => {
    if (permission !== 'media') { callback(uiPermissions.has(permission) && trusted(candidate, details)); return }
    callback(trusted(candidate, details)
      && Array.isArray(details?.mediaTypes) && details.mediaTypes.length > 0
      && details.mediaTypes.every(type => type === 'audio'))
  })
}

module.exports = { installSpeechPermissions }
