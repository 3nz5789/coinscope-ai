import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import DashboardLayout from "./components/DashboardLayout";
import Overview from "./pages/Overview";
import LiveScanner from "./pages/LiveScanner";
import Positions from "./pages/Positions";
import EquityCurve from "./pages/EquityCurve";
import Performance from "./pages/Performance";
import AlphaSignals from "./pages/AlphaSignals";
import RegimeState from "./pages/RegimeState";
import TradeJournal from "./pages/TradeJournal";
import RiskGate from "./pages/RiskGate";
import RecordingDaemon from "./pages/RecordingDaemon";

function Router() {
  return (
    <DashboardLayout>
      <Switch>
        <Route path="/" component={Overview} />
        <Route path="/scanner" component={LiveScanner} />
        <Route path="/positions" component={Positions} />
        <Route path="/equity" component={EquityCurve} />
        <Route path="/performance" component={Performance} />
        <Route path="/alpha" component={AlphaSignals} />
        <Route path="/regime" component={RegimeState} />
        <Route path="/journal" component={TradeJournal} />
        <Route path="/risk" component={RiskGate} />
        <Route path="/daemon" component={RecordingDaemon} />
        <Route path="/404" component={NotFound} />
        <Route component={NotFound} />
      </Switch>
    </DashboardLayout>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark">
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
