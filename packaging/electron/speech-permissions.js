/** Allow audio capture only for the main SugarAgent page on its loopback origin. */
function installSpeechPermissions(contents, resolveOrigin) {
  function trusted(candidate, details) {
    if (candidate !== contents || !details || details.isMainFrame !== true) return false
    try {
      return new URL(details.requestingUrl || details.requestingOrigin || contents.getURL()).origin === resolveOrigin()
    } catch { return false }
  }
  contents.session.setPermissionCheckHandler((candidate, permission, origin, details) => {
    // Preserve Electron's default approval for unrelated UI APIs such as clipboard writes.
    if (permission !== 'media') return true
    return trusted(candidate, { ...details, requestingOrigin: origin })
      && details?.mediaType === 'audio'
  })
  contents.session.setPermissionRequestHandler((candidate, permission, callback, details) => {
    if (permission !== 'media') { callback(true); return }
    callback(trusted(candidate, details)
      && Array.isArray(details?.mediaTypes) && details.mediaTypes.length > 0
      && details.mediaTypes.every(type => type === 'audio'))
  })
}

module.exports = { installSpeechPermissions }
