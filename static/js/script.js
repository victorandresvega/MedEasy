function initMap() {

    let defaultCenter = { lat: 18.200178, lng: -66.44513 };
    let defaultZoom = 9;
    let mapContainer = document.querySelector('.doctorCords');

    if (mapContainer) {
        let coordinates = mapContainer.getAttribute('data-coordinates');
        let [lat, lng] = coordinates.split(',').map(parseFloat);

        defaultCenter = { lat, lng };
        defaultZoom = 17;
    }

    map = new google.maps.Map(document.getElementById('map'), {
        center: defaultCenter,
        zoom: defaultZoom,
        mapId: '122517338e1e4a8'
    });

    let locations = getLocations();
    locations.forEach(cordinate_str => {
        let cordinate_lst = cordinate_str.split(',');
        let lat = parseFloat(cordinate_lst[0]);
        let lng = parseFloat(cordinate_lst[1]);
        let cordinate = { lat, lng };

        new google.maps.Marker({
            position: cordinate,
            map: map,
        });
    });
}

function getLocations() {
    let cords = [];
    let doctors = document.querySelectorAll(".doctorCords");
    doctors.forEach(doctor => {
        cords.push(doctor.getAttribute("data-coordinates"));
    });
    return cords;
}