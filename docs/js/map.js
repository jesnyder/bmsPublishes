var mapMaker = function functionMapMaker(setVars)

{

	//console.log('setVars = ')
	//console.log(setVars)


	var pubLayer = L.layerGroup();
	var adiposeLayer = L.layerGroup();
	var boneLayer = L.layerGroup();
	var cellsLayer = L.layerGroup();
	var evboostLayer = L.layerGroup();
	var exosomeLayer = L.layerGroup();
	var mediaLayer = L.layerGroup();
	var thesisLayer = L.layerGroup();
	var umbilical_cordLayer = L.layerGroup();


	//var mbAttr = 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>';
	var mbAttr = 'MapBox';
	var mbUrl = 'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw';


	var streets = L.tileLayer(mbUrl, {id: 'mapbox/streets-v11', tileSize: 512, zoomOffset: -1, attribution: mbAttr});

	var osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			maxZoom: 19,
			// attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
			attribution: ' '
		});


	//var map = L.map('map').setView([37.8, -96], 4);
	var map = L.map('map', {
			center: [10, 10],
			zoom: 2,
			minZoom: 2,
			maxZoom: 18,
			zoomSnap: 0.25,
			layers: [osm]
		});

		var baseLayers = {
			'OpenStreetMap': osm,
			'Streets': streets,
		};

		var overlays = {
			'2022 Pubs': pubLayer,
			'Adipose Pubs': adiposeLayer,
			'Bone Pubs': boneLayer,
			'Cells Pubs': cellsLayer,
			'EV Boost Pubs': evboostLayer,
			'Exosome Pubs': exosomeLayer,
			'Media Pubs': mediaLayer,
			//'Thesis Pubs': thesisLayer,
			'Umbilical Cord Pubs': umbilical_cordLayer,
			//'Background': background
		};

	var layerControl = L.control.layers(baseLayers, overlays).addTo(map);

	var satellite = L.tileLayer(mbUrl, {id: 'mapbox/satellite-v9', tileSize: 512, zoomOffset: -1, attribution: mbAttr});
		layerControl.addBaseLayer(satellite, 'Satellite');


	var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			maxZoom: 19,
			//attribution: '&copy; <a href="http://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'
			//attribution: ''
		}).addTo(map);


	// control that shows state info on hover
	var info = L.control();


	info.onAdd = function (map) {
			this._div = L.DomUtil.create('div', 'info');
			this.update();
			return this._div;
		};


	info.update = function (props) {
		this._div.innerHTML = (props ? '<b>' + props.LSAD + ' ' + props.NAME + '</b>' +
		'<br>$' + props['Income Level']['value'].toLocaleString("en-US") + ' Income Level' +
		'<br>$' + props['FMR']['value'].toLocaleString("en-US") + ' Fair Market Rent - Efficiency' +
		'<br>' +  Math.round(props['ratio']['value']*100) + '% FMR/Income' +
		'<br>' +  Math.round(props['slope']['value']*100000) + '% Slope'
		 :'<br> '
	 );
		};


	info.addTo(map);


function onEachTrial(feature, layer) {

				var aff = feature.properties.aff;
		    var url = feature.properties.url;
		    var title = feature.properties.title;

				map.createPane('popUpPane');
		    map.getPane('popUpPane').style.zIndex = 999;

		    var popupContent = '<p><b>'
		         + feature.properties.title
		         + '</b><br>'
		         + feature.properties.aff
		         + '<br> Cited by: '
						 + feature.properties.cites
		         + '<br>'
		         + '<a href="' + feature.properties.url + '" target="_blank" rel="noopener">'
		         + feature.properties.url + '</a>'
		         + '</p>';

		    if (feature.properties && feature.properties.popupContent) {
		            popupContent += feature.properties.popupContent;
		          }
		     layer.bindPopup(popupContent);
		  }


	function trialStyle (feature) {
		    return feature.properties && feature.properties.style;
				}


	function trialToLayer(feature, latlng) {

			var paneName = feature.properties.paneName;
			var zindex = feature.properties.zindex;
			//console.log('paneName = ')
			//console.log(paneName)
			//console.log('zindex = ')
			//console.log(zindex)

				map.createPane(paneName);
		    map.getPane(paneName).style.zIndex = zindex;
		    return L.circleMarker(latlng, {
		      radius: feature.properties.radius,
		      opacity:feature.properties.opacity,
		      fillOpacity: feature.properties.opacity,
		      fillColor: feature.properties.color,
		      color: 'black',
		      weight: 1,
		      pane: paneName,
		    });
		  }

	var pubLayer = L.geoJson(setVars.all, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
			}).addTo(map).addTo(pubLayer);

	var adiposeLayer = L.geoJson(setVars.adipose, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
		}).addTo(map).addTo(adiposeLayer);

	var boneLayer = L.geoJson(setVars.bone, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
		}).addTo(map).addTo(boneLayer);

	var cellsLayer = L.geoJson(setVars.cells, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
		}).addTo(map).addTo(cellsLayer);

	var evboostLayer = L.geoJson(setVars.evboost, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
		}).addTo(map).addTo(evboostLayer);

	var exosomeLayer = L.geoJson(setVars.exosome, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
		}).addTo(map).addTo(exosomeLayer);

	var mediaLayer = L.geoJson(setVars.media, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
		}).addTo(map).addTo(mediaLayer);

	var umbilical_cordLayer = L.geoJson(setVars.umbilical_cord, {
			style: trialStyle,
			onEachFeature: onEachTrial,
			pointToLayer: trialToLayer,
		}).addTo(map).addTo(umbilical_cordLayer);


};
