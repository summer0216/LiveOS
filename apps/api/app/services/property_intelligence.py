import json

from app.core.ai_client import ai_client
from app.models.property import Property
from app.models.property_analysis import PropertyAnalysis
from app.runtime.prompt import build_property_extraction_prompt


class PropertyIntelligence:
    def extract_json(
        self,
        description: str,
    ) -> str:
        """
        根据房源描述调用 LLM，
        返回原始 Property JSON 字符串。
        """

        prompt = build_property_extraction_prompt(
            description,
        )

        return ai_client.generate_json(prompt)

    def analyze(
        self,
        description: str,
    ) -> PropertyAnalysis:
        """
        根据房源描述生成 PropertyAnalysis。
        """

        json_text = self.extract_json(description)

        return self._build_analysis(json_text)

    def _build_analysis(
        self,
        json_text: str,
    ) -> PropertyAnalysis:
        """
        将 LLM 返回的 JSON 字符串转换为
        PropertyAnalysis。
        """

        data = self._parse_json(json_text)

        property_ = self._build_property(data)

        return PropertyAnalysis(
            property=property_,
        )

    def _parse_json(
        self,
        json_text: str,
    ) -> dict:
        """
        解析并验证 Property Intelligence 返回的 JSON。
        """

        data = json.loads(json_text)

        if not isinstance(data, dict):
            raise TypeError(
                "Property Intelligence response must be a JSON object.",
            )

        return data

    def _build_property(
        self,
        data: dict,
    ) -> Property:
        """
        将解析后的数据转换为 Property。
        """

        return Property(
            title=data.get("title"),
            district=data.get("district"),
            rent=data.get("rent"),
            area=data.get("area"),
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            commute_minutes=data.get("commute_minutes"),
            pet_friendly=data.get("pet_friendly"),
        )


property_intelligence = PropertyIntelligence()
