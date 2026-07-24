import {
  Chart, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend,
  BarElement, CategoryScale, LinearScale, ArcElement,
} from "chart.js";

Chart.register(
  RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend,
  BarElement, CategoryScale, LinearScale, ArcElement,
);
