from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated

from rest_framework.decorators import (
    authentication_classes,
    permission_classes,
    api_view,
)
from rest_framework import status
from rest_framework.response import Response

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.http import QueryDict
from relecov_core.api.serializers import (
    CreateDateAfterChangeStateSerializer,
    CreateSampleSerializer,
    CreateErrorSerializer,
    UpdateStateSampleSerializer,
)

from relecov_core.models import SampleState, Error


from relecov_core.api.utils.sample_handling import (
    split_sample_data,
)
from relecov_core.utils.handling_samples import get_sample_obj_from_sample_name

from relecov_core.api.utils.bioinfo_metadata_handling import (
    split_bioinfo_data,
    store_bioinfo_data,
    get_analysis_defined,
)

from relecov_core.api.utils.public_db_handling import store_pub_databases_data

from relecov_core.api.utils.variant_handling import (
    split_variant_data,
    store_variant_annotation,
    store_variant_in_sample,
    delete_created_variancs,
    variant_annotation_exists,
    get_variant_analysis_defined,
)

from relecov_core.api.utils.common_functions import (
    get_schema_version_if_exists,
    update_change_state_date,
)

from relecov_core.core_config import (
    ERROR_SAMPLE_NAME_NOT_INCLUDED,
    ERROR_SAMPLE_NOT_DEFINED,
    ERROR_VARIANT_INFORMATION_NOT_DEFINED,
    ERROR_ANALYSIS_ALREADY_DEFINED,
)


@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "analysis_authors": openapi.Schema(
                type=openapi.TYPE_STRING, description="Author of the analysis"
            ),
            "author_submitter": openapi.Schema(
                type=openapi.TYPE_STRING, description="Submitter author to GISAID"
            ),
            "authors": openapi.Schema(
                type=openapi.TYPE_STRING, description="Authors involved in the analysis"
            ),
            "experiment_alias": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experiment alias used for uploading to ENA",
            ),
            "experiment_title": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Experiment title for uploading to ENA",
            ),
            "fastq_r1_md5": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="MD5 for fastq R1 file",
            ),
            "fastq_r2_md5": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="MD5 for fastq R2 file",
            ),
            "gisaid_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Id given by GISAID",
            ),
            "microbiology_lab_sample_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Sample name ID given by the microbiology lab ",
            ),
            "r1_fastq_filepath": openapi.Schema(
                type=openapi.TYPE_STRING, description="Path where fastq R1 is stored"
            ),
            "r2_fastq_filepath": openapi.Schema(
                type=openapi.TYPE_STRING, description="Path where fastq R2 is stored"
            ),
            "sequence_file_R1_fastq": openapi.Schema(
                type=openapi.TYPE_STRING, description="File name of fastq R1"
            ),
            "sequence_file_R2_fastq": openapi.Schema(
                type=openapi.TYPE_STRING, description="File name of fastq R2"
            ),
            "sequencing_sample_id": openapi.Schema(
                type=openapi.TYPE_STRING, description="Project name"
            ),
            "study_alias": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Study alias used for uplading to ENA",
            ),
            "study_id": openapi.Schema(
                type=openapi.TYPE_STRING, description="Study ID for uploading to ENA"
            ),
            "study_title": openapi.Schema(
                type=openapi.TYPE_STRING, description="Study title for uploading to ENA"
            ),
            "study_type": openapi.Schema(
                type=openapi.TYPE_STRING, description="Study type for uploading to ENA"
            ),
            "submitting_lab_sample_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="sample name id given by the submitted lab",
            ),
        },
    ),
    responses={
        201: "Successful create information",
        400: "Bad Request",
        500: "Internal Server Error",
    },
)
@authentication_classes([SessionAuthentication, BasicAuthentication])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_sample_data(request):
    if request.method == "POST":
        data = request.data
        if isinstance(data, QueryDict):
            data = data.dict()

        schema_obj = get_schema_version_if_exists(data)
        schema_id = schema_obj.get_schema_id()
        if schema_obj is None:
            error = {"ERROR": "schema name and version is not defined"}
            return Response(error, status=status.HTTP_400_BAD_REQUEST)
        # check if sample id field and collecting_institution are in the request
        if "sequencing_sample_id" not in data or "collecting_institution" not in data:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        # check if sample is already defined
        if get_sample_obj_from_sample_name(data["sequencing_sample_id"]):
            error = {"ERROR": "sample already defined"}
            return Response(error, status=status.HTTP_400_BAD_REQUEST)
        # get the user to assign the sample based on the collecting_institution
        # value. If lab is not define user field is set t
        split_data = split_sample_data(data)
        # Add schema id to store in databasee
        split_data["sample"]["schema_obj"] = schema_id
        sample_serializer = CreateSampleSerializer(data=split_data["sample"])
        if not sample_serializer.is_valid():
            return Response(
                sample_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        sample_obj = sample_serializer.save()
        sample_id = sample_obj.get_sample_id()
        # update sample state date
        data = {
            "sampleID": sample_id,
            "stateID": split_data["sample"]["state"],
        }
        date_serilizer = CreateDateAfterChangeStateSerializer(data=data)
        if date_serilizer.is_valid():
            date_serilizer.save()

        # Save ENA info if included
        if len(split_data["ena"]) > 0:
            if (
                split_data["ena"]["ena_sample_accession"] != "Not Provided"
                and split_data["ena"]["ena_sample_accession"] != ""
            ):
                result = store_pub_databases_data(
                    split_data["ena"], "ena", schema_obj, sample_id
                )
                if "ERROR" in result:
                    return Response(result, status=status.HTTP_400_BAD_REQUEST)
                # Save entry in update state table
                sample_obj.update_state("Ena")
                state_id = (
                    SampleState.objects.filter(state__exact="Ena").last().get_state_id()
                )
                data = {"sampleID": sample_id, "stateID": state_id}
                date_serilizer = CreateDateAfterChangeStateSerializer(data=data)
                if date_serilizer.is_valid():
                    date_serilizer.save()
        # Save GISAID info if included
        if len(split_data["gisaid"]) > 0:
            if "EPI_ISL" in split_data["gisaid"]["gisaid_accession_id"]:
                result = store_pub_databases_data(
                    split_data["gisaid"], "gisaid", schema_obj, sample_id
                )
                if "ERROR" in result:
                    return Response(result, status=status.HTTP_400_BAD_REQUEST)
                # Save entry in update state table
                sample_obj.update_state("Gisaid")
                state_id = (
                    SampleState.objects.filter(state__exact="Gisaid")
                    .last()
                    .get_state_id()
                )
                data = {"sampleID": sample_id, "stateID": state_id}
                date_serilizer = CreateDateAfterChangeStateSerializer(data=data)
                if date_serilizer.is_valid():
                    date_serilizer.save()
        # Save AUTHOR info if included
        if len(split_data["author"]) > 0:
            result = store_pub_databases_data(
                split_data["author"], "author", schema_obj, sample_id
            )
            if "ERROR" in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response("Successful upload information", status=status.HTTP_201_CREATED)


@authentication_classes([SessionAuthentication, BasicAuthentication])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_bioinfo_metadata(request):
    if request.method == "POST":
        data = request.data

    if isinstance(data, QueryDict):
        data = data.dict()
    # check schema (name and version)
    schema_obj = get_schema_version_if_exists(data)
    if schema_obj is None:
        error = {"ERROR": "schema name and version is not defined"}
        return Response(error, status=status.HTTP_400_BAD_REQUEST)
    if "sequencing_sample_id" not in data:
        return Response(
            {"ERROR": ERROR_SAMPLE_NAME_NOT_INCLUDED},
            status=status.HTTP_400_BAD_REQUEST,
        )
    sample_obj = get_sample_obj_from_sample_name(data["sequencing_sample_id"])
    if sample_obj is None:
        return Response(
            {"ERROR": ERROR_SAMPLE_NOT_DEFINED}, status=status.HTTP_400_BAD_REQUEST
        )

    analysis_defined = get_analysis_defined(sample_obj)
    if data["analysis_date"] in list(analysis_defined):
        return Response(
            {"ERROR": ERROR_ANALYSIS_ALREADY_DEFINED},
            status=status.HTTP_400_BAD_REQUEST,
        )

    split_data = split_bioinfo_data(data, schema_obj)
    if "ERROR" in split_data:
        return Response(split_data, status=status.HTTP_400_BAD_REQUEST)

    stored_data = store_bioinfo_data(split_data, schema_obj)
    if "ERROR" in stored_data:
        return Response(stored_data, status=status.HTTP_400_BAD_REQUEST)
    state_id = SampleState.objects.filter(state__exact="Bioinfo").last().get_state_id()
    data_date = {"sampleID": sample_obj.get_sample_id(), "stateID": state_id}

    # update sample state
    sample_obj.update_state("Bioinfo")
    # Include date and state in DateState table
    date_serializer = CreateDateAfterChangeStateSerializer(data=data_date)
    if date_serializer.is_valid():
        date_serializer.save()

    return Response(status=status.HTTP_201_CREATED)


@authentication_classes([SessionAuthentication, BasicAuthentication])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_variant_data(request):
    if request.method == "POST":
        data = request.data
        if isinstance(data, QueryDict):
            data = data.dict()

        sample_obj = get_sample_obj_from_sample_name(data["sample_name"])
        if sample_obj is None:
            return Response(
                {"ERROR": ERROR_SAMPLE_NOT_DEFINED}, status=status.HTTP_400_BAD_REQUEST
            )
        analysis_defined = get_variant_analysis_defined(sample_obj)
        if data["analysis_date"] in list(analysis_defined):
            return Response(
                {"ERROR": ERROR_ANALYSIS_ALREADY_DEFINED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "variants" not in data:
            return Response(
                {"ERROR": ERROR_VARIANT_INFORMATION_NOT_DEFINED},
                status=status.HTTP_400_BAD_REQUEST,
            )
        found_error = False
        v_in_sample_list = []
        v_an_list = []

        for v_data in data["variants"]:
            split_data = split_variant_data(v_data, sample_obj, data["analysis_date"])

            if "ERROR" in split_data:
                error = {"ERROR": split_data}
                found_error = True
                break

            variant_in_sample_obj = store_variant_in_sample(
                split_data["variant_in_sample"]
            )

            if isinstance(variant_in_sample_obj, dict):
                error = {"ERROR": variant_in_sample_obj}
                found_error = True
                break

            v_in_sample_list.append(variant_in_sample_obj)

            if not variant_annotation_exists(split_data["variant_ann"]):
                variant_ann_obj = store_variant_annotation(split_data["variant_ann"])
                if isinstance(variant_ann_obj, dict):
                    error = {"ERROR": variant_ann_obj}
                    found_error = True
                    break

                v_an_list.append(variant_ann_obj)

        if found_error:
            delete_created_variancs(v_in_sample_list, v_an_list)
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        sample_obj.update_state("Variant")
        # Include date and state in DateState table
        state_id = (
            SampleState.objects.filter(state__exact="Variant").last().get_state_id()
        )
        sample_id = sample_obj.get_sample_id()
        update_change_state_date(sample_id, state_id)

        return Response(status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="put",
    operation_description="The PUT method is used to update existing records in the database.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "sample": openapi.Schema(
                type=openapi.TYPE_STRING, description="Number of Sample"
            ),
            "state": openapi.Schema(
                type=openapi.TYPE_STRING, description="Sample Status"
            ),
            "error_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="(Optional) If the status of the sample is ERROR, error_type tells us what type of error it is.",
            ),
        },
    ),
    responses={
        201: "Successful create information",
        400: "Bad Request",
        500: "Internal Server Error",
    },
)
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
@api_view(["PUT"])
def update_state(request):
    if request.method == "PUT":
        data = request.data
        if isinstance(data, QueryDict):
            data = data.dict()
        data["user"] = request.user.pk
        sample_obj = get_sample_obj_from_sample_name(data["sample_name"])
        if sample_obj is None:
            return Response(
                {"ERROR": ERROR_SAMPLE_NOT_DEFINED}, status=status.HTTP_400_BAD_REQUEST
            )
        sample_id = sample_obj.get_sample_id()
        # if state exists,
        if SampleState.objects.filter(state=data["state"]).exists():
            s_data = {
                "state": SampleState.objects.filter(state=data["state"])
                .last()
                .get_state_id()
            }
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        sample_serializer = UpdateStateSampleSerializer(sample_obj, data=s_data)
        if not sample_serializer.is_valid():
            return Response(
                sample_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        sample_serializer.save()

        if "error_type" in data and "Error" in data["state"]:
            error_type_id = (
                Error.objects.filter(error_name=data["error_type"])
                .last()
                .get_error_id()
            )
            e_data = {"error_type": error_type_id}
            sample_err_serializer = CreateErrorSerializer(sample_obj, data=e_data)
            if not sample_err_serializer.is_valid():
                return Response(
                    sample_err_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )
            sample_err_serializer.save()

        update_change_state_date(sample_id, s_data["state"])

        return Response("Successful upload information", status=status.HTTP_201_CREATED)
