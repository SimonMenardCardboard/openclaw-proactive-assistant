import SwiftUI

@main
struct TransmogrifierApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        // Initialize location tracking on app launch
        setupLocationTracking()
        
        return true
    }
    
    func applicationDidEnterBackground(_ application: UIApplication) {
        // Ensure location tracking continues in background
        LocationTracker.shared.startTracking()
    }
    
    private func setupLocationTracking() {
        // Check if already configured
        if UserDefaults.standard.string(forKey: "TransmogrifierAuthToken") == nil {
            print("⚠️  Location tracking not configured yet")
            print("   User needs to complete onboarding")
        } else {
            print("✅ Location tracking configured")
            
            // Request permissions if not already granted
            LocationTracker.shared.requestPermissions()
            
            // Start tracking
            LocationTracker.shared.startTracking()
        }
    }
}

struct ContentView: View {
    @State private var apiURL: String = UserDefaults.standard.string(forKey: "TransmogrifierAPIURL") ?? ""
    @State private var authToken: String = UserDefaults.standard.string(forKey: "TransmogrifierAuthToken") ?? ""
    @State private var isTracking: Bool = false
    @State private var statusMessage: String = "Not configured"
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Configuration")) {
                    TextField("API URL", text: $apiURL)
                        .textContentType(.URL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    
                    SecureField("Auth Token", text: $authToken)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    
                    Button("Save Configuration") {
                        saveConfiguration()
                    }
                    .disabled(apiURL.isEmpty || authToken.isEmpty)
                }
                
                Section(header: Text("Location Tracking")) {
                    HStack {
                        Text("Status")
                        Spacer()
                        Text(statusMessage)
                            .foregroundColor(isTracking ? .green : .gray)
                    }
                    
                    Button(isTracking ? "Stop Tracking" : "Start Tracking") {
                        toggleTracking()
                    }
                    .disabled(apiURL.isEmpty || authToken.isEmpty)
                }
                
                Section(header: Text("Permissions")) {
                    Button("Request Location Permission") {
                        LocationTracker.shared.requestPermissions()
                    }
                }
                
                Section(header: Text("About")) {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.gray)
                    }
                    
                    Link("Privacy Policy", destination: URL(string: "https://transmogrifier.app/privacy")!)
                    Link("Terms of Service", destination: URL(string: "https://transmogrifier.app/terms")!)
                }
            }
            .navigationTitle("Transmogrifier")
        }
        .onAppear {
            updateStatus()
        }
    }
    
    private func saveConfiguration() {
        LocationTracker.shared.configure(apiURL: apiURL, token: authToken)
        updateStatus()
    }
    
    private func toggleTracking() {
        if isTracking {
            LocationTracker.shared.stopTracking()
            isTracking = false
            statusMessage = "Stopped"
        } else {
            LocationTracker.shared.startTracking()
            isTracking = true
            statusMessage = "Tracking"
        }
    }
    
    private func updateStatus() {
        let hasConfig = !apiURL.isEmpty && !authToken.isEmpty
        statusMessage = hasConfig ? "Ready" : "Not configured"
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
