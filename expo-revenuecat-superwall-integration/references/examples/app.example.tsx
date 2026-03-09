import { SafeAreaView, Text, View } from "react-native";
import { MonetizationProviders } from "./monetization.shared";

function RootScreen() {
  return (
    <SafeAreaView style={{ flex: 1 }}>
      <View style={{ flex: 1, padding: 24, justifyContent: "center" }}>
        <Text style={{ fontSize: 22, fontWeight: "600" }}>
          Replace this screen tree with your real navigator or app content.
        </Text>
        <Text style={{ marginTop: 12, lineHeight: 22 }}>
          Keep monetization providers mounted once at the app root.
        </Text>
      </View>
    </SafeAreaView>
  );
}

export default function App() {
  return (
    <MonetizationProviders>
      <RootScreen />
    </MonetizationProviders>
  );
}
