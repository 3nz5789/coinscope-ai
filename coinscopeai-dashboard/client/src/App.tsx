import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Pages
import Overview from "./pages/Overview";
import Scanner from "./pages/Scanner";
import Positions from "./pages/Positions";
import Journal from "./pages/Journal";
import Performance from "./pages/Performance";
import EquityCurve from "./pages/EquityCurve";
import RiskGate from "./pages/RiskGate";
import RegimeDetection from "./pages/RegimeDetection";
import PositionSizer from "./pages/PositionSizer";
import AlphaSignals from "./pages/AlphaSignals";
import MarketData from "./pages/MarketData";
import BacktestResults from "./pages/BacktestResults";
import Settings from "./pages/Settings";
import Pricing from "./pages/Pricing";
import SystemStatus from "./pages/SystemStatus";
import Alerts from "./pages/Alerts";
import Decisions from "./pages/Decisions";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Overview} />
      <Route path="/scanner" component={Scanner} />
      <Route path="/positions" component={Positions} />
      <Route path="/journal" component={Journal} />
      <Route path="/performance" component={Performance} />
      <Route path="/equity" component={EquityCurve} />
      <Route path="/risk-gate" component={RiskGate} />
      <Route path="/regime" component={RegimeDetection} />
      <Route path="/position-sizer" component={PositionSizer} />
      <Route path="/alpha" component={AlphaSignals} />
      <Route path="/market-data" component={MarketData} />
      <Route path="/backtest" component={BacktestResults} />
      <Route path="/settings" component={Settings} />
      <Route path="/pricing" component={Pricing} />
      <Route path="/system-status" component={SystemStatus} />
      <Route path="/alerts" component={Alerts} />
      <Route path="/decisions" component={Decisions} />
      <Route path="/404" component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider defaultTheme="dark">
          <TooltipProvider>
            <Toaster />
            <Router />
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
