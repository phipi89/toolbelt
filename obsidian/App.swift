import AppKit
import UniformTypeIdentifiers

private let fallbackLinkName = "temporarily linked.md"
private let markdownType = UTType("net.daringfireball.markdown")!

private enum OpenerError: LocalizedError {
  case missingFile(String)
  case missingFallbackVault(String)
  case invalidURI(String)
  case associationFailed(String)

  var errorDescription: String? {
    switch self {
    case .missingFile(let path):
      return "File does not exist: \(path)"
    case .missingFallbackVault(let path):
      return "Fallback Obsidian vault does not exist: \(path)"
    case .invalidURI(let path):
      return "Could not create an Obsidian URI for: \(path)"
    case .associationFailed(let message):
      return "Could not associate Markdown files: \(message)"
    }
  }
}

private func percentEncode(_ value: String) -> String {
  value.utf8.map { byte in
    switch byte {
    case 48...57, 65...90, 97...122, 45, 46, 95, 126:
      return String(UnicodeScalar(byte))
    default:
      return String(format: "%%%02X", byte)
    }
  }.joined()
}

private func obsidianURI(for fileURL: URL) throws -> URL {
  let value = "obsidian://open?path=\(percentEncode(fileURL.path))"
  guard let url = URL(string: value) else {
    throw OpenerError.invalidURI(fileURL.path)
  }
  return url
}

private func containingVault(for fileURL: URL) -> URL? {
  let fileManager = FileManager.default
  var directory = fileURL.deletingLastPathComponent()

  while directory.path != "/" {
    if fileManager.fileExists(atPath: directory.appendingPathComponent(".obsidian").path) {
      return directory
    }
    directory.deleteLastPathComponent()
  }
  return nil
}

private func fallbackVaultURL() -> URL {
  if let path = ProcessInfo.processInfo.environment["OBSIDIAN_FALLBACK_VAULT"] {
    return URL(fileURLWithPath: path).standardizedFileURL
  }
  return FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent("Documents/obsidian_base", isDirectory: true)
}

private func accessibleURL(for path: String) throws -> URL {
  let fileManager = FileManager.default
  let fileURL = URL(fileURLWithPath: path).standardizedFileURL
  guard fileManager.fileExists(atPath: fileURL.path) else {
    throw OpenerError.missingFile(fileURL.path)
  }

  if containingVault(for: fileURL) != nil {
    return fileURL
  }

  let vaultURL = fallbackVaultURL()
  guard
    fileManager.fileExists(
      atPath: vaultURL.appendingPathComponent(".obsidian", isDirectory: true).path
    )
  else {
    throw OpenerError.missingFallbackVault(vaultURL.path)
  }

  let linkURL = vaultURL.appendingPathComponent(fallbackLinkName)
  try? fileManager.removeItem(at: linkURL)
  try fileManager.createSymbolicLink(at: linkURL, withDestinationURL: fileURL)
  return linkURL
}

private func openPaths(_ paths: [String], dryRun: Bool = false) throws {
  for path in paths {
    let uri = try obsidianURI(for: accessibleURL(for: path))
    if dryRun {
      print(uri.absoluteString)
    } else if !NSWorkspace.shared.open(uri) {
      throw OpenerError.invalidURI(path)
    }
  }
}

private func associateMarkdown(with appPath: String) throws {
  let appURL = URL(fileURLWithPath: appPath).standardizedFileURL
  var finished = false
  var associationError: Error?

  NSWorkspace.shared.setDefaultApplication(
    at: appURL,
    toOpen: markdownType
  ) { error in
    associationError = error
    finished = true
  }

  while !finished {
    RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.05))
  }
  if let associationError {
    throw OpenerError.associationFailed(associationError.localizedDescription)
  }
}

private final class AppDelegate: NSObject, NSApplicationDelegate {
  func application(_ sender: NSApplication, openFiles filenames: [String]) {
    do {
      try openPaths(filenames)
      sender.reply(toOpenOrPrint: .success)
    } catch {
      sender.reply(toOpenOrPrint: .failure)
      NSAlert(error: error).runModal()
    }
    sender.terminate(nil)
  }
}

private func fail(_ error: Error) -> Never {
  FileHandle.standardError.write(Data("\(error.localizedDescription)\n".utf8))
  exit(1)
}

let arguments = Array(CommandLine.arguments.dropFirst())
if arguments.first == "--default-handler" {
  if let url = NSWorkspace.shared.urlForApplication(toOpen: markdownType) {
    print(url.path)
    exit(0)
  }
  fail(OpenerError.associationFailed("no Markdown handler is registered"))
}

if arguments.first == "--associate" {
  guard arguments.count == 2 else {
    fail(OpenerError.associationFailed("expected an application path"))
  }
  do {
    try associateMarkdown(with: arguments[1])
    exit(0)
  } catch {
    fail(error)
  }
}

if arguments.first == "--dry-run" {
  do {
    try openPaths(Array(arguments.dropFirst()), dryRun: true)
    exit(0)
  } catch {
    fail(error)
  }
}

if !arguments.isEmpty {
  do {
    try openPaths(arguments)
    exit(0)
  } catch {
    fail(error)
  }
}

private let app = NSApplication.shared
private let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
