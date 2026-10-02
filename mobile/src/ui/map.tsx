/** Карта (Leaflet внутри WebView): те же подложки, что на сайте — MapTiler (если ключ задан в админке) → OpenStreetMap.
 *  Метки и «я здесь» передаются из приложения; нажатие на метку — onSelect(id). */
import { createElement, useEffect, useMemo, useRef } from 'react';
import { Platform, View } from 'react-native';
import { WebView } from 'react-native-webview';

import { API_URL } from '@/lib/api';
import { useApp } from '@/state/app';

export type Marker = { id: number; lat: number; lon: number; title: string; sub?: string; mosque?: boolean };

export function PlacesMap({ center, me, markers, onSelect, onMove }: {
  center: { lat: number; lon: number }; me?: { lat: number; lon: number } | null; markers: Marker[];
  onSelect: (id: number) => void; onMove?: (bbox: [number, number, number, number]) => void;
}) {
  const { config, dark, c, t } = useApp();
  const more = JSON.stringify(t('Подробнее') + ' →');
  const web = useRef<WebView>(null);
  const key = config?.map?.maptiler ?? '';
  const html = useMemo(() => `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<link rel="stylesheet" href="${API_URL}/static/vendor/leaflet/leaflet.css">
<style>html,body,#m{margin:0;height:100%;background:${c.bg}}.pin{width:30px;height:30px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${c.accent};border:3px solid #fff;box-shadow:0 2px 6px #0005}
.pin.mosque{background:#12a150}.me{width:16px;height:16px;border-radius:50%;background:#1e88e5;border:3px solid #fff;box-shadow:0 0 0 6px #1e88e533}
.leaflet-popup-content{font:14px -apple-system,Roboto,sans-serif}.leaflet-popup-content b{display:block;margin-bottom:2px}</style></head>
<body><div id="m"></div><script src="${API_URL}/static/vendor/leaflet/leaflet.js"></script><script>
var map=L.map('m',{zoomControl:false,attributionControl:true}).setView([${center.lat},${center.lon}],13);
var tiles=${JSON.stringify(key)}?[{u:'https://api.maptiler.com/maps/${dark ? 'streets-v2-dark' : 'streets-v2'}/256/{z}/{x}/{y}.png?key='+encodeURIComponent(${JSON.stringify(key)}),a:'© MapTiler © OpenStreetMap'}]:[];
tiles.push({u:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',a:'© OpenStreetMap'});
var i=0,layer;function use(){if(layer)map.removeLayer(layer);var t=tiles[i];layer=L.tileLayer(t.u,{maxZoom:19,attribution:t.a});var bad=0;
layer.on('tileerror',function(){if(++bad>3&&i<tiles.length-1){i++;use();}});layer.addTo(map);}use();
var group=L.layerGroup().addTo(map),meL=null;
function send(o){window.ReactNativeWebView&&window.ReactNativeWebView.postMessage(JSON.stringify(o));}
map.on('moveend',function(){var b=map.getBounds();send({t:'move',b:[b.getSouth(),b.getWest(),b.getNorth(),b.getEast()]});});
window.setData=function(d){group.clearLayers();d.markers.forEach(function(p){var m=L.marker([p.lat,p.lon],{icon:L.divIcon({className:'',html:'<div class="pin'+(p.mosque?' mosque':'')+'"></div>',iconSize:[30,30],iconAnchor:[15,30],popupAnchor:[0,-28]})});
m.bindPopup('<b>'+p.title.replace(/</g,'&lt;')+'</b>'+(p.sub||'').replace(/</g,'&lt;')+'<br><a href="#" onclick="send({t:\\'open\\',id:'+p.id+'});return false">'+${more}+'</a>');m.addTo(group);});
if(d.me){if(meL)map.removeLayer(meL);meL=L.marker([d.me.lat,d.me.lon],{icon:L.divIcon({className:'',html:'<div class="me"></div>',iconSize:[16,16],iconAnchor:[8,8]})}).addTo(map);}};
window.goTo=function(lat,lon){map.setView([lat,lon],14);};
send({t:'ready'});
</script></body></html>`, [key, dark, c.accent, c.bg, more]); // eslint-disable-line react-hooks/exhaustive-deps

  const push = () => web.current?.injectJavaScript(`window.setData && window.setData(${JSON.stringify({ markers, me })});true;`);
  useEffect(push, [markers, me]);  
  useEffect(() => {
    web.current?.injectJavaScript(`window.goTo && window.goTo(${center.lat},${center.lon});true;`);
  }, [center.lat, center.lon]);

  if (Platform.OS === 'web') {
    // веб-версия (для проверки на ПК): та же карта во фрейме, метки подставляются сразу
    const doc = html.replace("send({t:'ready'});", `window.setData(${JSON.stringify({ markers, me })});`);
    return (
      <View style={{ flex: 1, borderRadius: 22, overflow: 'hidden' }}>
        {createElement('iframe', { srcDoc: doc, style: { border: 0, width: '100%', height: '100%' } })}
      </View>
    );
  }
  return (
    <View style={{ flex: 1, borderRadius: 22, overflow: 'hidden', backgroundColor: c.card2 }}>
      <WebView ref={web} originWhitelist={['*']} source={{ html, baseUrl: API_URL }} style={{ flex: 1, backgroundColor: 'transparent' }}
        onMessage={(e) => {
          try {
            const d = JSON.parse(e.nativeEvent.data);
            if (d.t === 'ready') push();
            else if (d.t === 'open') onSelect(d.id);
            else if (d.t === 'move' && onMove) onMove(d.b);
          } catch {
            /* чужое сообщение */
          }
        }} />
    </View>
  );
}
