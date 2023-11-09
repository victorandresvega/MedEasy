function initMap(coordinates){
    map = new google.maps.Map(document.getElementById('map'), {
        zoom: 10,
        });

    coordinates = new google.maps.Latlng(coordinates.latitude,coordinates.longitude);

    map.setCenter(coordinates);

    marker = new google.maps.marker({
        position: coordinates,
        map: map 
    });

}


