import {markup} from './view.js?v=20261031-native';
import {mountBrowserSettings} from './app.js?v=20261031-native';

document.querySelector('main.setup').innerHTML=markup;
mountBrowserSettings(document);
