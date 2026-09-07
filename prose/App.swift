import AppKit
import UniformTypeIdentifiers

private let autosaveDelay: TimeInterval = 0.25
private let baseFontSize: CGFloat = 25
private let minimumFontSize: CGFloat = 14
private let maximumFontSize: CGFloat = 96
private let maximumColumnWidth: CGFloat = 680

@MainActor
private final class GlyphBoundLayoutManager: NSLayoutManager {
    override func fillBackgroundRectArray(
        _ rectArray: UnsafePointer<NSRect>,
        count rectCount: Int,
        forCharacterRange charRange: NSRange,
        color: NSColor
    ) {
        guard let textContainer = textContainers.first,
              let textView = textContainer.textView
        else {
            super.fillBackgroundRectArray(
                rectArray,
                count: rectCount,
                forCharacterRange: charRange,
                color: color
            )
            return
        }

        let origin = textView.textContainerOrigin
        var trimmedRects: [NSRect] = []
        for sourceRect in UnsafeBufferPointer(start: rectArray, count: rectCount) {
            let containerRect = sourceRect.offsetBy(dx: -origin.x, dy: -origin.y)
            let glyphRange = glyphRange(forBoundingRect: containerRect, in: textContainer)
            enumerateLineFragments(forGlyphRange: glyphRange) { [self] _, _, _, lineGlyphRange, _ in
                var lineCharacterRange = characterRange(
                    forGlyphRange: lineGlyphRange,
                    actualGlyphRange: nil
                )
                if let string = textStorage?.string as NSString? {
                    while lineCharacterRange.length > 0 {
                        let finalCharacter = string.character(
                            at: NSMaxRange(lineCharacterRange) - 1
                        )
                        guard finalCharacter == 10 || finalCharacter == 13 else { break }
                        lineCharacterRange.length -= 1
                    }
                }
                guard lineCharacterRange.length > 0 else { return }

                let visibleGlyphRange = self.glyphRange(
                    forCharacterRange: lineCharacterRange,
                    actualCharacterRange: nil
                )
                let glyphRect = boundingRect(
                    forGlyphRange: visibleGlyphRange,
                    in: textContainer
                )
                let lineTextRect = NSRect(
                    x: glyphRect.minX + origin.x,
                    y: sourceRect.minY,
                    width: glyphRect.width,
                    height: sourceRect.height
                )
                let clippedRect = sourceRect.intersection(lineTextRect)
                if !clippedRect.isNull && clippedRect.width > 0 {
                    trimmedRects.append(clippedRect)
                }
            }
        }

        trimmedRects.withUnsafeBufferPointer { buffer in
            guard let baseAddress = buffer.baseAddress else { return }
            super.fillBackgroundRectArray(
                baseAddress,
                count: buffer.count,
                forCharacterRange: charRange,
                color: color
            )
        }
    }
}

@MainActor
private final class DraggableStrip: NSView {
    override func mouseDown(with event: NSEvent) {
        window?.performDrag(with: event)
    }
}

@MainActor
private final class ProseTextView: NSTextView {
    var zoomHandler: ((CGFloat) -> Void)?
    var italicHandler: (() -> Void)?
    var monospaceHandler: (() -> Void)?
    var saveHandler: (() -> Void)?
    var expandsTabs = false

    override func insertTab(_ sender: Any?) {
        if expandsTabs {
            insertText("    ", replacementRange: selectedRange())
        } else {
            super.insertTab(sender)
        }
    }

    override func performKeyEquivalent(with event: NSEvent) -> Bool {
        guard event.modifierFlags.intersection(.deviceIndependentFlagsMask).contains(.command),
              let characters = event.charactersIgnoringModifiers
        else {
            return super.performKeyEquivalent(with: event)
        }

        if characters == "+" || characters == "=" {
            zoomHandler?(2)
            return true
        }
        if characters == "-" {
            zoomHandler?(-2)
            return true
        }
        if characters.lowercased() == "z" {
            if event.modifierFlags.contains(.shift) {
                undoManager?.redo()
            } else {
                undoManager?.undo()
            }
            return true
        }
        if characters.lowercased() == "a" && event.modifierFlags.contains(.shift) {
            let pasteboard = NSPasteboard.general
            pasteboard.clearContents()
            pasteboard.setString(string, forType: .string)
            window?.performClose(nil)
            return true
        }
        if characters.lowercased() == "a" {
            selectAll(nil)
            return true
        }
        if characters.lowercased() == "c" {
            copy(nil)
            return true
        }
        if characters.lowercased() == "v" {
            paste(nil)
            return true
        }
        if characters.lowercased() == "x" {
            cut(nil)
            return true
        }
        if characters.lowercased() == "i" {
            italicHandler?()
            return true
        }
        if characters.lowercased() == "u" {
            monospaceHandler?()
            return true
        }
        if characters.lowercased() == "s" {
            saveHandler?()
            return true
        }
        return super.performKeyEquivalent(with: event)
    }
}

@MainActor
private final class DocumentWindowController: NSWindowController, NSWindowDelegate, NSTextViewDelegate {
    let fileURL: URL
    private let textView: ProseTextView
    private let scrollView: NSScrollView
    private var saveTimer: Timer?
    private var fontSize = baseFontSize
    private var isItalic = false
    private var isMonospaced = false
    private var isLoading = true
    private var isFinalized = false
    private var associatedURL: URL?
    var onClose: (() -> Void)?

    init(fileURL: URL, backgroundColor: NSColor) throws {
        self.fileURL = fileURL

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 780, height: 640),
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Prose"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.titlebarSeparatorStyle = .none
        window.backgroundColor = backgroundColor
        window.isMovableByWindowBackground = true
        window.hasShadow = true
        window.minSize = NSSize(width: 420, height: 320)
        window.standardWindowButton(.closeButton)?.isHidden = false
        window.standardWindowButton(.miniaturizeButton)?.isHidden = true
        window.standardWindowButton(.zoomButton)?.isHidden = true

        let textStorage = NSTextStorage()
        let layoutManager = GlyphBoundLayoutManager()
        let textContainer = NSTextContainer(
            containerSize: NSSize(width: maximumColumnWidth, height: CGFloat.greatestFiniteMagnitude)
        )
        textStorage.addLayoutManager(layoutManager)
        layoutManager.addTextContainer(textContainer)
        let textView = ProseTextView(frame: window.contentLayoutRect, textContainer: textContainer)
        self.textView = textView
        textView.isRichText = false
        textView.importsGraphics = false
        textView.drawsBackground = false
        textView.isHorizontallyResizable = false
        textView.isVerticallyResizable = true
        textView.autoresizingMask = [.width]
        textView.textContainer?.widthTracksTextView = false
        textView.textContainer?.heightTracksTextView = false
        textView.textContainer?.lineFragmentPadding = 0
        textView.textColor = NSColor(calibratedWhite: 0.13, alpha: 1)
        textView.insertionPointColor = NSColor(calibratedWhite: 0.13, alpha: 1)
        textView.selectedTextAttributes = [
            .backgroundColor: NSColor(calibratedWhite: 0.13, alpha: 0.16)
        ]
        textView.isAutomaticQuoteSubstitutionEnabled = true
        textView.isAutomaticDashSubstitutionEnabled = true
        textView.isAutomaticTextReplacementEnabled = true
        textView.isContinuousSpellCheckingEnabled = true

        let scrollView = NSScrollView(frame: window.contentLayoutRect)
        self.scrollView = scrollView
        scrollView.autoresizingMask = [.width, .height]
        scrollView.drawsBackground = false
        scrollView.borderType = .noBorder
        scrollView.hasVerticalScroller = false
        scrollView.hasHorizontalScroller = false
        scrollView.automaticallyAdjustsContentInsets = false
        scrollView.documentView = textView

        let rootView = NSView(frame: window.contentLayoutRect)
        rootView.wantsLayer = true
        rootView.layer?.backgroundColor = backgroundColor.cgColor
        let draggableStrip = DraggableStrip()
        scrollView.translatesAutoresizingMaskIntoConstraints = false
        draggableStrip.translatesAutoresizingMaskIntoConstraints = false
        rootView.addSubview(scrollView)
        rootView.addSubview(draggableStrip)
        NSLayoutConstraint.activate([
            draggableStrip.topAnchor.constraint(equalTo: rootView.topAnchor),
            draggableStrip.leadingAnchor.constraint(equalTo: rootView.leadingAnchor),
            draggableStrip.trailingAnchor.constraint(equalTo: rootView.trailingAnchor),
            draggableStrip.heightAnchor.constraint(equalToConstant: 32),
            scrollView.topAnchor.constraint(equalTo: draggableStrip.bottomAnchor),
            scrollView.leadingAnchor.constraint(equalTo: rootView.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: rootView.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: rootView.bottomAnchor)
        ])
        window.contentView = rootView

        super.init(window: window)
        window.delegate = self
        textView.delegate = self
        textView.zoomHandler = { [weak self] delta in self?.changeFontSize(by: delta) }
        textView.italicHandler = { [weak self] in self?.toggleItalic() }
        textView.monospaceHandler = { [weak self] in self?.toggleMonospace() }
        textView.saveHandler = { [weak self] in self?.saveAssociatedFile() }

        let contents = try String(contentsOf: fileURL, encoding: .utf8)
        textView.string = contents
        applyTypography()
        textView.allowsUndo = true
        textView.undoManager?.removeAllActions()
        isLoading = false

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(viewportDidChange),
            name: NSView.frameDidChangeNotification,
            object: scrollView.contentView
        )
        scrollView.contentView.postsFrameChangedNotifications = true
        updateLayout()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    func present() {
        window?.center()
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        textView.window?.makeFirstResponder(textView)
    }

    func textDidChange(_ notification: Notification) {
        guard !isLoading else { return }
        updateLayout()
        saveTimer?.invalidate()
        saveTimer = Timer.scheduledTimer(
            timeInterval: autosaveDelay,
            target: self,
            selector: #selector(save),
            userInfo: nil,
            repeats: false
        )
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        moveToRecents()
        return true
    }

    func windowWillClose(_ notification: Notification) {
        saveTimer?.invalidate()
        onClose?()
    }

    @objc func save() {
        guard !isFinalized else { return }
        saveTimer?.invalidate()
        saveTimer = nil
        do {
            try textView.string.write(to: fileURL, atomically: true, encoding: .utf8)
        } catch {
            presentError(error)
        }
    }

    @objc private func viewportDidChange() {
        updateLayout()
    }

    func moveToRecents() {
        guard !isFinalized else { return }
        save()
        let rootURL = fileURL.deletingLastPathComponent().deletingLastPathComponent()
        let recentURL = rootURL.appendingPathComponent("recent", isDirectory: true)
            .appendingPathComponent(fileURL.lastPathComponent)
        do {
            try FileManager.default.createDirectory(
                at: recentURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try FileManager.default.moveItem(at: fileURL, to: recentURL)
            isFinalized = true
        } catch {
            presentError(error)
        }
    }

    private func changeFontSize(by delta: CGFloat) {
        fontSize = min(maximumFontSize, max(minimumFontSize, fontSize + delta))
        applyTypography()
        updateLayout()
    }

    private func toggleItalic() {
        isItalic.toggle()
        applyTypography()
        updateLayout()
    }

    private func toggleMonospace() {
        isMonospaced.toggle()
        if isMonospaced {
            isItalic = false
        }
        applyTypography()
        updateLayout()
    }

    private func saveAssociatedFile() {
        if let associatedURL {
            saveText(to: associatedURL)
            return
        }

        guard let window else { return }
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.plainText]
        panel.canCreateDirectories = true
        panel.isExtensionHidden = false
        panel.nameFieldStringValue = "Prose.txt"
        panel.beginSheetModal(for: window) { [weak self] response in
            guard response == .OK, let self, let destination = panel.url else { return }
            self.saveText(to: destination)
        }
    }

    private func saveText(to destination: URL) {
        do {
            try textView.string.write(
                to: destination,
                atomically: true,
                encoding: .utf8
            )
            associatedURL = destination
            window?.representedURL = destination
            window?.title = destination.lastPathComponent
            window?.subtitle = destination.deletingLastPathComponent().lastPathComponent
            window?.titleVisibility = .visible
        } catch {
            presentError(error)
        }
    }

    private func applyTypography() {
        textView.expandsTabs = isMonospaced
        let regularFont: NSFont
        if isMonospaced {
            regularFont = NSFont.monospacedSystemFont(ofSize: fontSize, weight: .regular)
        } else {
            let fontName = isItalic ? "EBGaramond-Italic" : "EBGaramond-Regular"
            regularFont = NSFont(name: fontName, size: fontSize)
                ?? NSFont.systemFont(ofSize: fontSize)
        }
        let font = isMonospaced && isItalic
            ? NSFontManager.shared.convert(regularFont, toHaveTrait: .italicFontMask)
            : regularFont
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = isMonospaced ? .left : .center
        let lineHeightScale: CGFloat = isMonospaced ? 1.2 : 1.05
        let lineHeight = ceil(font.ascender - font.descender + font.leading) * lineHeightScale
        paragraph.minimumLineHeight = lineHeight
        paragraph.maximumLineHeight = lineHeight

        let range = NSRange(location: 0, length: textView.textStorage?.length ?? 0)
        textView.font = font
        textView.textStorage?.setAttributes([
            .font: font,
            .foregroundColor: textView.textColor ?? NSColor.textColor,
            .paragraphStyle: paragraph
        ], range: range)
        textView.typingAttributes = [
            .font: font,
            .foregroundColor: textView.textColor ?? NSColor.textColor,
            .paragraphStyle: paragraph
        ]
        textView.defaultParagraphStyle = paragraph
        textView.alignment = paragraph.alignment
    }

    private func updateLayout() {
        guard let textContainer = textView.textContainer,
              let layoutManager = textView.layoutManager
        else { return }

        let viewport = scrollView.contentView.bounds.size
        let columnWidth = min(maximumColumnWidth, max(220, viewport.width - 96))
        textContainer.containerSize = NSSize(
            width: columnWidth,
            height: CGFloat.greatestFiniteMagnitude
        )
        layoutManager.ensureLayout(for: textContainer)
        let laidOutHeight = max(
            layoutManager.usedRect(for: textContainer).maxY,
            layoutManager.extraLineFragmentRect.maxY
        )
        let textHeight = max(fontSize * 1.2, laidOutHeight)
        let horizontalInset = max(48, (viewport.width - columnWidth) / 2)
        let verticalInset = max(64, (viewport.height - textHeight) / 2)
        textView.textContainerInset = NSSize(width: horizontalInset, height: verticalInset)
        textView.frame = NSRect(
            origin: .zero,
            size: NSSize(width: viewport.width, height: max(viewport.height, textHeight + verticalInset * 2))
        )
    }
}

@MainActor
private final class AppDelegate: NSObject, NSApplicationDelegate {
    private var documents: [String: DocumentWindowController] = [:]
    private var paletteIndex = Int.random(in: 0..<AppDelegate.palette.count)

    private static let palette: [NSColor] = [
        NSColor(calibratedRed: 0.97, green: 0.87, blue: 0.65, alpha: 1),
        NSColor(calibratedRed: 0.72, green: 0.87, blue: 0.76, alpha: 1),
        NSColor(calibratedRed: 0.67, green: 0.82, blue: 0.92, alpha: 1),
        NSColor(calibratedRed: 0.94, green: 0.73, blue: 0.72, alpha: 1),
        NSColor(calibratedRed: 0.79, green: 0.73, blue: 0.91, alpha: 1),
        NSColor(calibratedRed: 0.96, green: 0.78, blue: 0.59, alpha: 1),
        NSColor(calibratedRed: 0.65, green: 0.86, blue: 0.86, alpha: 1),
        NSColor(calibratedRed: 0.90, green: 0.70, blue: 0.82, alpha: 1)
    ]

    func applicationDidFinishLaunching(_ notification: Notification) {
        installMenu()
        for argument in CommandLine.arguments.dropFirst() where !argument.hasPrefix("-psn_") {
            do {
                try openDocument(at: URL(fileURLWithPath: argument))
            } catch {
                NSApp.presentError(error)
            }
        }
    }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        var failed = false
        for filename in filenames {
            do {
                try openDocument(at: URL(fileURLWithPath: filename))
            } catch {
                failed = true
                NSApp.presentError(error)
            }
        }
        sender.reply(toOpenOrPrint: failed ? .failure : .success)
    }

    func applicationShouldOpenUntitledFile(_ sender: NSApplication) -> Bool {
        false
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        documents.values.forEach { $0.moveToRecents() }
        return .terminateNow
    }

    private func openDocument(at url: URL) throws {
        let key = url.standardizedFileURL.path
        if let existing = documents[key] {
            existing.present()
            return
        }

        let color = Self.palette[paletteIndex % Self.palette.count]
        paletteIndex += 1
        let controller = try DocumentWindowController(fileURL: url, backgroundColor: color)
        controller.onClose = { [weak self] in self?.documents.removeValue(forKey: key) }
        documents[key] = controller
        controller.present()
    }

    private func installMenu() {
        let mainMenu = NSMenu()

        let appItem = NSMenuItem()
        mainMenu.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Quit Prose", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let fileItem = NSMenuItem()
        mainMenu.addItem(fileItem)
        let fileMenu = NSMenu(title: "File")
        let closeItem = fileMenu.addItem(
            withTitle: "Close",
            action: #selector(closeKeyWindow(_:)),
            keyEquivalent: "w"
        )
        closeItem.target = self
        fileItem.submenu = fileMenu

        NSApp.mainMenu = mainMenu
    }

    @objc private func closeKeyWindow(_ sender: Any?) {
        NSApp.keyWindow?.performClose(sender)
    }
}

let application = NSApplication.shared
private let appDelegate = MainActor.assumeIsolated { AppDelegate() }
application.delegate = appDelegate
application.setActivationPolicy(.regular)
application.run()
