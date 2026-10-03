/** Карта (Leaflet внутри WebView): те же подложки, что на сайте — MapTiler (если ключ задан в админке) → OpenStreetMap.
 *  Метки и «я здесь» передаются из приложения; нажатие на метку — onSelect(id). */
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { createElement, useEffect, useMemo, useRef } from 'react';
import { Platform, View } from 'react-native';
import { WebView } from 'react-native-webview';

import { API_URL } from '@/lib/api';
import { PLACE_SVG } from '@/lib/placeIcons';
import { useApp } from '@/state/app';

export type Marker = { id: number; lat: number; lon: number; title: string; sub?: string; mosque?: boolean; icon?: string; kind?: string; selected?: boolean };

export function PlacesMap({ center, me, markers, onSelect, onMove, rounded = true }: {
  center: { lat: number; lon: number }; me?: { lat: number; lon: number } | null; markers: Marker[];
  onSelect: (id: number) => void; onMove?: (bbox: [number, number, number, number]) => void; rounded?: boolean;
}) {
  const { config, dark, c, t } = useApp();
  const more = JSON.stringify(t('Подробнее') + ' →');
  const web = useRef<WebView>(null);
  const key = config?.map?.maptiler ?? '';
  const html = useMemo(() => `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<link rel="stylesheet" href="${API_URL}/static/vendor/leaflet/leaflet.css">
<style>html,body,#m{margin:0;height:100%;background:${c.bg}}.pin{width:30px;height:30px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${c.accent};border:3px solid #fff;box-shadow:0 2px 6px #0005}
.pin.mosque{background:#12a150}.mp{width:36px;height:36px;border-radius:50% 50% 50% 4px;transform:rotate(-45deg);background:#fff;border:2.5px solid ${c.accent};display:flex;align-items:center;justify-content:center;box-shadow:0 5px 12px -4px #0008}
.mp span{transform:rotate(45deg);display:flex;color:${c.accent}}.mp.mosque{border-color:#0e8f57}.mp.mosque span{color:#0e8f57}.mp.cafe{border-color:#f59e0b}.mp.cafe span{color:#d97706}.mp.shop{border-color:#2a8fdc}.mp.shop span{color:#2a8fdc}.mp.butcher{border-color:#e5484d}.mp.butcher span{color:#e5484d}.mp.hotel{border-color:#8b5cf6}.mp.hotel span{color:#8b5cf6}
.mp.on{transform:rotate(-45deg) scale(1.25)}.cl{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:${c.accent};color:#fff;font:800 15px -apple-system,Roboto,sans-serif;border:4px solid #fff9;box-shadow:0 5px 14px -5px #0009}
.me{width:16px;height:16px;border-radius:50%;background:#1e88e5;border:3px solid #fff;box-shadow:0 0 0 6px #1e88e533}
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
var last=null,IC=${JSON.stringify(PLACE_SVG)};
function esc(x){return String(x==null?'':x).replace(/[&<>"]/g,function(ch){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch];});}
function draw(){if(!last)return;group.clearLayers();var cell=54,g={};last.markers.forEach(function(p){var pt=map.latLngToContainerPoint([p.lat,p.lon]);var k=Math.floor(pt.x/cell)+':'+Math.floor(pt.y/cell);(g[k]=g[k]||[]).push(p);});
Object.keys(g).forEach(function(k){var a=g[k];if(a.length===1||map.getZoom()>=17){a.forEach(function(p){var cls='mp '+esc(p.kind||(p.mosque?'mosque':''))+(p.selected?' on':'');
L.marker([p.lat,p.lon],{icon:L.divIcon({className:'',html:'<div class="'+cls+'"><span>'+(IC[p.icon]||IC.place)+'</span></div>',iconSize:[36,42],iconAnchor:[18,40]})}).on('click',function(){send({t:'open',id:p.id});}).addTo(group);});return;}
var la=0,lo=0;a.forEach(function(p){la+=p.lat;lo+=p.lon;});la/=a.length;lo/=a.length;
L.marker([la,lo],{icon:L.divIcon({className:'',html:'<div class="cl">'+a.length+'</div>',iconSize:[42,42],iconAnchor:[21,21]})}).on('click',function(){map.fitBounds(L.latLngBounds(a.map(function(p){return [p.lat,p.lon];})),{padding:[60,60],maxZoom:17});}).addTo(group);});}
map.on('zoomend',draw);
window.setData=function(d){last=d;draw();
if(d.me){if(meL)map.removeLayer(meL);meL=L.marker([d.me.lat,d.me.lon],{interactive:false,icon:L.divIcon({className:'',html:'<div class="me"></div>',iconSize:[16,16],iconAnchor:[8,8]})}).addTo(map);}};
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
      <View style={{ flex: 1, borderRadius: rounded ? 22 : 0, overflow: 'hidden' }}>
        {createElement('iframe', { srcDoc: doc, style: { border: 0, width: '100%', height: '100%' } })}
      </View>
    );
  }
  return (
    <View style={{ flex: 1, borderRadius: rounded ? 22 : 0, overflow: 'hidden', backgroundColor: c.card2 }}>
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

const PLACE_ICON: Record<string, { name: keyof typeof MaterialCommunityIcons.glyphMap; color: string }> = {
  mosque: { name: 'mosque', color: '#0e8f57' }, cafe: { name: 'silverware-fork-knife', color: '#d97706' }, shop: { name: 'shopping-outline', color: '#2a8fdc' },
  hotel: { name: 'bed-outline', color: '#8b5cf6' }, butcher: { name: 'food-steak', color: '#e5484d' }, place: { name: 'map-marker-outline', color: '#6d5efc' },
};

/** Значок категории места (в списке и фильтрах) — те же ключи, что отдаёт сервер в поле icon. */
export function PlaceIcon({ icon, size = 20, color }: { icon?: string; size?: number; color?: string }) {
  const x = PLACE_ICON[icon ?? 'place'] ?? PLACE_ICON.place;
  return <MaterialCommunityIcons name={x.name} size={size} color={color ?? x.color} />;
}
