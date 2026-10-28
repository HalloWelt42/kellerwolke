import "./app.css";
import "@fontsource/barlow/400.css";
import "@fontsource/barlow/500.css";
import "@fontsource/barlow/600.css";
import "@fortawesome/fontawesome-free/css/all.min.css";
import { mount } from "svelte";
import { themaAnwenden } from "./lib/thema.svelte";
import { heilenBeiFehlernBeobachten } from "./lib/medien/lesezugang.svelte";
import App from "./App.svelte";

themaAnwenden();
heilenBeiFehlernBeobachten();

const app = mount(App, { target: document.getElementById("app")! });

export default app;
